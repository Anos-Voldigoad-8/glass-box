"""Anthropic SDK wrapper for GLASS BOX - automatic tracing of Anthropic API calls."""

from __future__ import annotations

import functools
import logging
from typing import Any, Optional, TYPE_CHECKING

from .client import GlassboxClient, get_client
from .context import get_current_trace, get_current_span
from .types import Span, SpanStatus, SpanType, TokenUsage, calculate_cost
from .pricing import calculate_cost as dynamic_calculate_cost, normalize_provider

if TYPE_CHECKING:
    from anthropic import Anthropic as AnthropicClient
    from anthropic import AsyncAnthropic as AsyncAnthropicClient

logger = logging.getLogger(__name__)


class TracedAnthropic:
    """Wrapper around Anthropic client that automatically traces all API calls."""

    def __init__(
        self,
        client: "AnthropicClient",
        glassbox_client: Optional[GlassboxClient] = None,
        trace_name: str = "anthropic.call",
    ):
        self._client = client
        self._glassbox_client = glassbox_client or get_client()
        self._trace_name = trace_name

    @property
    def client(self) -> "AnthropicClient":
        """Access the underlying Anthropic client."""
        return self._client

    def _create_llm_span(
        self,
        model: str,
        messages: list[dict],
        response: Any,
        operation: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> Span:
        """Create a span for an LLM call."""
        from .context import get_current_trace, get_current_span

        current_trace = get_current_trace()
        current_span = get_current_span()

        # Extract token usage from Anthropic response
        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage_obj = response.usage
            usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "input_tokens", 0),
                completion_tokens=getattr(usage_obj, "output_tokens", 0),
                total_tokens=getattr(usage_obj, "input_tokens", 0) + getattr(usage_obj, "output_tokens", 0),
                model=getattr(response, "model", model),
            )

        # Calculate cost using dynamic pricing
        cost = 0.0
        if usage:
            try:
                cost = dynamic_calculate_cost("anthropic", model, usage.prompt_tokens, usage.completion_tokens)
                usage.cost_usd = cost
            except Exception:
                # Fallback to legacy pricing
                cost = calculate_cost(model, usage.prompt_tokens, usage.completion_tokens)
                usage.cost_usd = cost

        span = Span(
            id=f"{operation}-{id(response)}",
            trace_id=current_trace.id if current_trace else f"trace-{id(response)}",
            parent_id=current_span.id if current_span else None,
            name=f"{self._trace_name}:{operation}",
            span_type=SpanType.LLM_CALL,
            metadata={
                "model": model,
                "provider": "anthropic",
                "operation": operation,
                "messages": messages,
                "system": system,
                "response_preview": str(response)[:1000],
                "cost_usd": cost,
                **kwargs,
            },
        )

        if usage:
            span.add_token_usage(usage)

        span.finish(SpanStatus.SUCCESS)

        if current_trace:
            current_trace.add_span(span)
        else:
            self._glassbox_client.add_span(span)

        return span

    def messages_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace messages.create calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        system = kwargs.get("system", None)

        response = self._client.messages.create(*args, **kwargs)

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="messages.create",
            system=system,
        )

        return response

    def messages_stream(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace messages.stream calls (returns a stream manager)."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        system = kwargs.get("system", None)

        # For streaming, we need to wrap the stream
        stream = self._client.messages.stream(*args, **kwargs)

        # We'll create the span when the stream completes
        # This requires wrapping the stream context manager
        return TracedStream(stream, self, model, messages, operation="messages.stream", system=system)

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying client."""
        return getattr(self._client, name)


class TracedAsyncAnthropic:
    """Wrapper around AsyncAnthropic client that automatically traces all API calls."""

    def __init__(
        self,
        client: "AsyncAnthropicClient",
        glassbox_client: Optional[GlassboxClient] = None,
        trace_name: str = "anthropic.call",
    ):
        self._client = client
        self._glassbox_client = glassbox_client or get_client()
        self._trace_name = trace_name

    @property
    def client(self) -> "AsyncAnthropicClient":
        """Access the underlying AsyncAnthropic client."""
        return self._client

    async def messages_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace messages.create calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        system = kwargs.get("system", None)

        response = await self._client.messages.create(*args, **kwargs)

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="messages.create",
            system=system,
        )

        return response

    async def messages_stream(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace messages.stream calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        system = kwargs.get("system", None)

        stream = await self._client.messages.stream(*args, **kwargs)
        return TracedAsyncStream(stream, self, model, messages, operation="messages.stream", system=system)

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying client."""
        return getattr(self._client, name)


class TracedStream:
    """Wrapper for Anthropic stream that creates a span on completion."""

    def __init__(
        self,
        stream: Any,
        tracer: TracedAnthropic,
        model: str,
        messages: list[dict],
        operation: str,
        system: str | None = None,
    ):
        self._stream = stream
        self._tracer = tracer
        self._model = model
        self._messages = messages
        self._operation = operation
        self._system = system
        self._response = None

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Get the final response from the stream
        if hasattr(self._stream, "get_final_response"):
            self._response = self._stream.get_final_response()
            if self._response:
                self._tracer._create_llm_span(
                    model=self._model,
                    messages=self._messages,
                    response=self._response,
                    operation=self._operation,
                    system=self._system,
                )
        return self._stream.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        """Delegate to the underlying stream."""
        return getattr(self._stream, name)

    def __iter__(self):
        return iter(self._stream)


class TracedAsyncStream:
    """Wrapper for Anthropic async stream that creates a span on completion."""

    def __init__(
        self,
        stream: Any,
        tracer: TracedAsyncAnthropic,
        model: str,
        messages: list[dict],
        operation: str,
        system: str | None = None,
    ):
        self._stream = stream
        self._tracer = tracer
        self._model = model
        self._messages = messages
        self._operation = operation
        self._system = system
        self._response = None

    async def __aenter__(self):
        await self._stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self._stream, "get_final_response"):
            self._response = await self._stream.get_final_response()
            if self._response:
                self._tracer._create_llm_span(
                    model=self._model,
                    messages=self._messages,
                    response=self._response,
                    operation=self._operation,
                    system=self._system,
                )
        return await self._stream.__aexit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __aiter__(self):
        return self._stream.__aiter__()


def wrap_anthropic(
    client: "AnthropicClient",
    glassbox_client: Optional[GlassboxClient] = None,
    trace_name: str = "anthropic.call",
) -> TracedAnthropic:
    """Wrap an Anthropic client to automatically trace API calls.

    Usage:
        from anthropic import Anthropic
        import glassbox as gb

        client = Anthropic()
        traced_client = gb.wrap_anthropic(client)

        # Now all calls are automatically traced
        response = traced_client.messages.create(...)
    """
    return TracedAnthropic(client, glassbox_client, trace_name)


def wrap_async_anthropic(
    client: "AsyncAnthropicClient",
    glassbox_client: Optional[GlassboxClient] = None,
    trace_name: str = "anthropic.call",
) -> TracedAsyncAnthropic:
    """Wrap an AsyncAnthropic client to automatically trace API calls.

    Usage:
        from anthropic import AsyncAnthropic
        import glassbox as gb

        client = AsyncAnthropic()
        traced_client = gb.wrap_async_anthropic(client)

        # Now all calls are automatically traced
        response = await traced_client.messages.create(...)
    """
    return TracedAsyncAnthropic(client, glassbox_client, trace_name)


def patch_anthropic(glassbox_client: Optional[GlassboxClient] = None) -> None:
    """Patch the Anthropic module globally to auto-trace all calls.

    Usage:
        import glassbox as gb
        gb.patch_anthropic()

        from anthropic import Anthropic
        client = Anthropic()  # Automatically traced
    """
    try:
        import anthropic

        original_anthropic_init = anthropic.Anthropic.__init__
        original_async_anthropic_init = anthropic.AsyncAnthropic.__init__

        @functools.wraps(original_anthropic_init)
        def traced_anthropic_init(self, *args, **kwargs):
            original_anthropic_init(self, *args, **kwargs)
            wrapped = TracedAnthropic(self, glassbox_client)
            self.messages.create = wrapped.messages_create
            self.messages.stream = wrapped.messages_stream

        @functools.wraps(original_async_anthropic_init)
        def traced_async_anthropic_init(self, *args, **kwargs):
            original_async_anthropic_init(self, *args, **kwargs)
            wrapped = TracedAsyncAnthropic(self, glassbox_client)
            self.messages.create = wrapped.messages_create
            self.messages.stream = wrapped.messages_stream

        anthropic.Anthropic.__init__ = traced_anthropic_init
        anthropic.AsyncAnthropic.__init__ = traced_async_anthropic_init

        logger.info("Anthropic module patched for automatic tracing")

    except ImportError:
        logger.warning("Anthropic not installed, skipping patch")
    except Exception as e:
        logger.error(f"Failed to patch Anthropic: {e}")


__all__ = [
    "TracedAnthropic",
    "TracedAsyncAnthropic",
    "wrap_anthropic",
    "wrap_async_anthropic",
    "patch_anthropic",
]