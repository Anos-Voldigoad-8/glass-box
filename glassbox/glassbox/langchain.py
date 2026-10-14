"""LangChain callback handler for GLASS BOX - automatic tracing of LangChain operations."""

from __future__ import annotations

import logging
import threading
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Union

from .client import GlassboxClient, get_client
from .context import get_current_trace, get_current_span, set_current_span
from .types import (
    LogEvent,
    Span,
    SpanStatus,
    SpanType,
    TokenUsage,
    Trace,
    TraceStatus,
)
from .pricing import calculate_cost as dynamic_calculate_cost, normalize_provider

if False:  # TYPE_CHECKING
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Thread-local storage for tracking nested calls
_local = threading.local()


def _get_callback_state() -> Dict[str, Any]:
    """Get or create callback state for current thread."""
    if not hasattr(_local, "glassbox_state"):
        _local.glassbox_state = {
            "active_spans": [],
            "current_trace": None,
            "span_stack": [],
        }
    return _local.glassbox_state


class GlassboxCallbackHandler:
    """LangChain callback handler that automatically traces all operations to GLASS BOX.

    Usage:
        from langchain.callbacks import CallbackManager
        from glassbox import GlassboxCallbackHandler

        handler = GlassboxCallbackHandler()
        callback_manager = CallbackManager([handler])

        # Use with any LangChain component
        chain = LLMChain(llm=llm, prompt=prompt, callback_manager=callback_manager)
        result = chain.run("Hello")

    Or globally:
        import langchain
        langchain.callbacks.set_global_callbacks([GlassboxCallbackHandler()])
    """

    def __init__(
        self,
        glassbox_client: Optional[GlassboxClient] = None,
        trace_name: str = "langchain.run",
        capture_inputs: bool = True,
        capture_outputs: bool = True,
        capture_metadata: bool = True,
    ):
        self.glassbox_client = glassbox_client or get_client()
        self.trace_name = trace_name
        self.capture_inputs = capture_inputs
        self.capture_outputs = capture_outputs
        self.capture_metadata = capture_metadata

        # State for tracking nested operations
        self._trace: Optional[Trace] = None
        self._span_stack: List[Span] = []

    def _get_or_create_trace(self) -> Trace:
        """Get existing trace or create a new one."""
        if self._trace is None:
            current_trace = get_current_trace()
            if current_trace:
                self._trace = current_trace
            else:
                self._trace = Trace(
                    id=str(uuid.uuid4()),
                    name=self.trace_name,
                    agent_name="langchain",
                    metadata={"source": "langchain_callback"},
                )
        return self._trace

    def _create_span(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        parent: Optional[Span] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Create a new span and add it to the trace."""
        trace = self._get_or_create_trace()
        parent_id = parent.id if parent else (self._span_stack[-1].id if self._span_stack else None)

        span = Span(
            id=str(uuid.uuid4()),
            trace_id=trace.id,
            parent_id=parent_id,
            name=name,
            span_type=span_type,
            metadata=metadata or {},
        )

        trace.add_span(span)
        self._span_stack.append(span)
        set_current_span(span)

        return span

    def _finish_span(
        self,
        span: Span,
        status: SpanStatus = SpanStatus.SUCCESS,
        error: Optional[str] = None,
    ) -> None:
        """Finish a span and pop from stack."""
        span.finish(status, error)
        if self._span_stack and self._span_stack[-1] == span:
            self._span_stack.pop()
        if self._span_stack:
            set_current_span(self._span_stack[-1])
        else:
            set_current_span(None)

    # ===== LLM Callbacks =====

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts."""
        model_name = serialized.get("name", serialized.get("id", ["unknown"]))[-1] if serialized else "unknown"
        if isinstance(model_name, list):
            model_name = model_name[-1]

        span = self._create_span(
            name=f"llm:{model_name}",
            span_type=SpanType.LLM_CALL,
            metadata={
                "model": model_name,
                "provider": "langchain",
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "tags": tags,
                "serialized": serialized if self.capture_metadata else None,
                "prompts": prompts if self.capture_inputs else None,
            },
        )

        # Store run_id -> span mapping for later retrieval
        state = _get_callback_state()
        state.setdefault("llm_spans", {})[str(run_id)] = span

    def on_llm_end(
        self,
        response: "LLMResult",
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends successfully."""
        state = _get_callback_state()
        span = state.get("llm_spans", {}).pop(str(run_id), None)

        if span is None:
            # Fallback: find the most recent LLM span
            for s in reversed(self._span_stack):
                if s.span_type == SpanType.LLM_CALL:
                    span = s
                    break

        if span is None:
            return

        # Extract token usage from LangChain response
        usage = None
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                model = response.llm_output.get("model_name", span.metadata.get("model", "unknown"))
                usage = TokenUsage(
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    total_tokens=token_usage.get("total_tokens", 0),
                    model=model,
                )

        # Calculate cost
        if usage:
            model = usage.model
            try:
                cost = dynamic_calculate_cost("langchain", model, usage.prompt_tokens, usage.completion_tokens)
            except Exception:
                from .types import calculate_cost
                cost = calculate_cost(model, usage.prompt_tokens, usage.completion_tokens)
            usage.cost_usd = cost
            span.metadata["cost_usd"] = cost

        if usage:
            span.add_token_usage(usage)

        if self.capture_outputs:
            span.metadata["generations"] = [
                {
                    "text": gen.text if hasattr(gen, "text") else str(gen),
                    "generation_info": gen.generation_info if hasattr(gen, "generation_info") else None,
                }
                for gen in response.generations[0]
            ] if response.generations else []

        self._finish_span(span, SpanStatus.SUCCESS)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
        state = _get_callback_state()
        span = state.get("llm_spans", {}).pop(str(run_id), None)

        if span is None:
            for s in reversed(self._span_stack):
                if s.span_type == SpanType.LLM_CALL:
                    span = s
                    break

        if span:
            self._finish_span(span, SpanStatus.ERROR, str(error))

    # ===== Chain Callbacks =====

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain starts."""
        chain_name = serialized.get("name", serialized.get("id", ["chain"]))[-1] if serialized else "chain"
        if isinstance(chain_name, list):
            chain_name = chain_name[-1]

        span = self._create_span(
            name=f"chain:{chain_name}",
            span_type=SpanType.AGENT_STEP,
            metadata={
                "chain_name": chain_name,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "tags": tags,
                "inputs": inputs if self.capture_inputs else None,
            },
        )

        state = _get_callback_state()
        state.setdefault("chain_spans", {})[str(run_id)] = span

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain ends successfully."""
        state = _get_callback_state()
        span = state.get("chain_spans", {}).pop(str(run_id), None)

        if span is None:
            for s in reversed(self._span_stack):
                if s.span_type == SpanType.AGENT_STEP and s.metadata.get("run_id") == str(run_id):
                    span = s
                    break

        if span:
            if self.capture_outputs:
                span.metadata["outputs"] = outputs
            self._finish_span(span, SpanStatus.SUCCESS)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain errors."""
        state = _get_callback_state()
        span = state.get("chain_spans", {}).pop(str(run_id), None)

        if span:
            self._finish_span(span, SpanStatus.ERROR, str(error))

    # ===== Tool Callbacks =====

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool starts."""
        tool_name = serialized.get("name", serialized.get("id", ["tool"]))[-1] if serialized else "tool"
        if isinstance(tool_name, list):
            tool_name = tool_name[-1]

        span = self._create_span(
            name=f"tool:{tool_name}",
            span_type=SpanType.TOOL_CALL,
            metadata={
                "tool_name": tool_name,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "tags": tags,
                "input": input_str if self.capture_inputs else None,
            },
        )

        state = _get_callback_state()
        state.setdefault("tool_spans", {})[str(run_id)] = span

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool ends successfully."""
        state = _get_callback_state()
        span = state.get("tool_spans", {}).pop(str(run_id), None)

        if span:
            if self.capture_outputs:
                span.metadata["output"] = output
            self._finish_span(span, SpanStatus.SUCCESS)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool errors."""
        state = _get_callback_state()
        span = state.get("tool_spans", {}).pop(str(run_id), None)

        if span:
            self._finish_span(span, SpanStatus.ERROR, str(error))

    # ===== Agent Callbacks =====

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        tool_name = getattr(action, "tool", "unknown")
        tool_input = getattr(action, "tool_input", {})

        span = self._create_span(
            name=f"agent_action:{tool_name}",
            span_type=SpanType.AGENT_STEP,
            metadata={
                "tool": tool_name,
                "tool_input": tool_input,
                "log": getattr(action, "log", ""),
                "run_id": str(run_id),
            },
        )

        state = _get_callback_state()
        state.setdefault("agent_spans", {})[str(run_id)] = span

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        state = _get_callback_state()
        span = state.get("agent_spans", {}).pop(str(run_id), None)

        if span:
            if self.capture_outputs:
                span.metadata["output"] = getattr(finish, "return_values", {})
                span.metadata["log"] = getattr(finish, "log", "")
            self._finish_span(span, SpanStatus.SUCCESS)

    # ===== Retriever Callbacks =====

    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever starts."""
        retriever_name = serialized.get("name", serialized.get("id", ["retriever"]))[-1] if serialized else "retriever"
        if isinstance(retriever_name, list):
            retriever_name = retriever_name[-1]

        span = self._create_span(
            name=f"retriever:{retriever_name}",
            span_type=SpanType.TOOL_CALL,
            metadata={
                "retriever_name": retriever_name,
                "query": query if self.capture_inputs else None,
                "run_id": str(run_id),
            },
        )

        state = _get_callback_state()
        state.setdefault("retriever_spans", {})[str(run_id)] = span

    def on_retriever_end(
        self,
        documents: List[Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever ends successfully."""
        state = _get_callback_state()
        span = state.get("retriever_spans", {}).pop(str(run_id), None)

        if span:
            if self.capture_outputs:
                span.metadata["documents_count"] = len(documents)
                span.metadata["documents_preview"] = [
                    doc.page_content[:200] if hasattr(doc, "page_content") else str(doc)[:200]
                    for doc in documents[:5]
                ]
            self._finish_span(span, SpanStatus.SUCCESS)

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever errors."""
        state = _get_callback_state()
        span = state.get("retriever_spans", {}).pop(str(run_id), None)

        if span:
            self._finish_span(span, SpanStatus.ERROR, str(error))

    # ===== Text/Chat Model Callbacks (for streaming) =====

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts."""
        # Similar to on_llm_start but for chat models
        self.on_llm_start(serialized, [str(m) for m in messages[0]] if messages else [],
                         run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)

    # ===== Utility Methods =====

    def get_trace(self) -> Optional[Trace]:
        """Get the current trace (if any)."""
        return self._trace

    def finish_trace(self, status: TraceStatus = TraceStatus.SUCCESS, error: Optional[str] = None) -> Optional[Trace]:
        """Finish the current trace and send to backend."""
        if self._trace:
            # Finish any remaining spans
            while self._span_stack:
                span = self._span_stack.pop()
                if span.status == SpanStatus.RUNNING:
                    span.finish(SpanStatus.SUCCESS)

            self._trace.finish(status, error)
            self.glassbox_client.add_trace(self._trace)

            trace = self._trace
            self._trace = None
            self._span_stack.clear()
            return trace
        return None

    def __enter__(self) -> "GlassboxCallbackHandler":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - finish trace."""
        status = TraceStatus.ERROR if exc_type else TraceStatus.SUCCESS
        self.finish_trace(status, str(exc_val) if exc_val else None)


# Convenience function for easy integration
def get_langchain_callback(
    glassbox_client: Optional[GlassboxClient] = None,
    **kwargs: Any,
) -> GlassboxCallbackHandler:
    """Get a GlassboxCallbackHandler instance for LangChain integration.

    Usage:
        from langchain.chains import LLMChain
        from glassbox import get_langchain_callback

        callback = get_langchain_callback()
        chain = LLMChain(llm=llm, prompt=prompt, callbacks=[callback])
    """
    return GlassboxCallbackHandler(glassbox_client=glassbox_client, **kwargs)


# Try to inherit from BaseCallbackHandler if LangChain is available
try:
    from langchain_core.callbacks import BaseCallbackHandler

    class _GlassboxCallbackHandlerWithBase(GlassboxCallbackHandler, BaseCallbackHandler):
        """GlassboxCallbackHandler that inherits from BaseCallbackHandler for LangChain compatibility."""
        pass

    # Replace the original class
    GlassboxCallbackHandler = _GlassboxCallbackHandlerWithBase
    logger.debug("GlassboxCallbackHandler now inherits from BaseCallbackHandler")
except ImportError:
    logger.debug("LangChain not installed, GlassboxCallbackHandler will work as standalone")


__all__ = [
    "GlassboxCallbackHandler",
    "get_langchain_callback",
]