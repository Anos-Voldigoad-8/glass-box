"""OpenAI SDK wrapper for GLASS BOX - automatic tracing of OpenAI API calls."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Optional, TYPE_CHECKING

from .client import GlassboxClient, get_client
from .context import get_current_trace, get_current_span
from .types import Span, SpanStatus, SpanType, TokenUsage, calculate_cost
from .pricing import calculate_cost as dynamic_calculate_cost, normalize_provider

if TYPE_CHECKING:
    from openai import OpenAI as OpenAIClient
    from openai import AsyncOpenAI as AsyncOpenAIClient

logger = logging.getLogger(__name__)


class TracedOpenAI:
    """Wrapper around OpenAI client that automatically traces all API calls."""

    def __init__(
        self,
        client: "OpenAIClient",
        glassbox_client: Optional[GlassboxClient] = None,
        trace_name: str = "openai.call",
    ):
        self._client = client
        self._glassbox_client = glassbox_client or get_client()
        self._trace_name = trace_name

    @property
    def client(self) -> "OpenAIClient":
        """Access the underlying OpenAI client."""
        return self._client

    def _create_llm_span(
        self,
        model: str,
        messages: list[dict],
        response: Any,
        operation: str,
        **kwargs: Any,
    ) -> Span:
        """Create a span for an LLM call."""
        from .context import get_current_trace, get_current_span

        current_trace = get_current_trace()
        current_span = get_current_span()

        # Extract token usage
        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage_obj = response.usage
            usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0),
                completion_tokens=getattr(usage_obj, "completion_tokens", 0),
                total_tokens=getattr(usage_obj, "total_tokens", 0),
                model=getattr(response, "model", model),
            )

        # Calculate cost using dynamic pricing
        cost = 0.0
        if usage:
            try:
                cost = dynamic_calculate_cost("openai", model, usage.prompt_tokens, usage.completion_tokens)
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
                "provider": "openai",
                "operation": operation,
                "messages": messages,
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

    def chat_completions_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace chat.completions.create calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")

        response = self._client.chat.completions.create(*args, **kwargs)

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="chat.completions.create",
        )

        return response

    def completions_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace completions.create calls."""
        prompt = kwargs.get("prompt", "")
        model = kwargs.get("model", "unknown")

        response = self._client.completions.create(*args, **kwargs)

        # Convert prompt to messages format for consistency
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="completions.create",
        )

        return response

    def embeddings_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace embeddings.create calls."""
        input_text = kwargs.get("input", "")
        model = kwargs.get("model", "unknown")

        response = self._client.embeddings.create(*args, **kwargs)

        # For embeddings, we don't have a completion, just token usage
        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage_obj = response.usage
            usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=getattr(usage_obj, "total_tokens", 0),
                model=getattr(response, "model", model),
            )

        cost = 0.0
        if usage:
            try:
                cost = dynamic_calculate_cost("openai", model, usage.prompt_tokens, 0)
                usage.cost_usd = cost
            except Exception:
                cost = calculate_cost(model, usage.prompt_tokens, 0)
                usage.cost_usd = cost

        from .context import get_current_trace, get_current_span
        current_trace = get_current_trace()
        current_span = get_current_span()

        span = Span(
            id=f"embedding-{id(response)}",
            trace_id=current_trace.id if current_trace else f"trace-{id(response)}",
            parent_id=current_span.id if current_span else None,
            name=f"{self._trace_name}:embeddings.create",
            span_type=SpanType.LLM_CALL,
            metadata={
                "model": model,
                "provider": "openai",
                "operation": "embeddings.create",
                "input_preview": str(input_text)[:500],
                "cost_usd": cost,
            },
        )

        if usage:
            span.add_token_usage(usage)

        span.finish(SpanStatus.SUCCESS)

        if current_trace:
            current_trace.add_span(span)
        else:
            self._glassbox_client.add_span(span)

        return response

    def beta_chat_completions_parse(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace beta.chat.completions.parse calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")

        response = self._client.beta.chat.completions.parse(*args, **kwargs)

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="beta.chat.completions.parse",
        )

        return response

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying client."""
        return getattr(self._client, name)


class TracedAsyncOpenAI:
    """Wrapper around AsyncOpenAI client that automatically traces all API calls."""

    def __init__(
        self,
        client: "AsyncOpenAIClient",
        glassbox_client: Optional[GlassboxClient] = None,
        trace_name: str = "openai.call",
    ):
        self._client = client
        self._glassbox_client = glassbox_client or get_client()
        self._trace_name = trace_name

    @property
    def client(self) -> "AsyncOpenAIClient":
        """Access the underlying AsyncOpenAI client."""
        return self._client

    async def chat_completions_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace chat.completions.create calls."""
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")

        response = await self._client.chat.completions.create(*args, **kwargs)

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="chat.completions.create",
        )

        return response

    async def completions_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace completions.create calls."""
        prompt = kwargs.get("prompt", "")
        model = kwargs.get("model", "unknown")

        response = await self._client.completions.create(*args, **kwargs)

        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt

        self._create_llm_span(
            model=model,
            messages=messages,
            response=response,
            operation="completions.create",
        )

        return response

    async def embeddings_create(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Trace embeddings.create calls."""
        input_text = kwargs.get("input", "")
        model = kwargs.get("model", "unknown")

        response = await self._client.embeddings.create(*args, **kwargs)

        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage_obj = response.usage
            usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=getattr(usage_obj, "total_tokens", 0),
                model=getattr(response, "model", model),
            )

        cost = 0.0
        if usage:
            try:
                cost = dynamic_calculate_cost("openai", model, usage.prompt_tokens, 0)
                usage.cost_usd = cost
            except Exception:
                cost = calculate_cost(model, usage.prompt_tokens, 0)
                usage.cost_usd = cost

        from .context import get_current_trace, get_current_span
        current_trace = get_current_trace()
        current_span = get_current_span()

        span = Span(
            id=f"embedding-{id(response)}",
            trace_id=current_trace.id if current_trace else f"trace-{id(response)}",
            parent_id=current_span.id if current_span else None,
            name=f"{self._trace_name}:embeddings.create",
            span_type=SpanType.LLM_CALL,
            metadata={
                "model": model,
                "provider": "openai",
                "operation": "embeddings.create",
                "input_preview": str(input_text)[:500],
                "cost_usd": cost,
            },
        )

        if usage:
            span.add_token_usage(usage)

        span.finish(SpanStatus.SUCCESS)

        if current_trace:
            current_trace.add_span(span)
        else:
            self._glassbox_client.add_span(span)

        return response

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying client."""
        return getattr(self._client, name)


def wrap_openai(
    client: "OpenAIClient",
    glassbox_client: Optional[GlassboxClient] = None,
    trace_name: str = "openai.call",
) -> TracedOpenAI:
    """Wrap an OpenAI client to automatically trace API calls.

    Usage:
        from openai import OpenAI
        import glassbox as gb

        client = OpenAI()
        traced_client = gb.wrap_openai(client)

        # Now all calls are automatically traced
        response = traced_client.chat.completions.create(...)
    """
    return TracedOpenAI(client, glassbox_client, trace_name)


def wrap_async_openai(
    client: "AsyncOpenAIClient",
    glassbox_client: Optional[GlassboxClient] = None,
    trace_name: str = "openai.call",
) -> TracedAsyncOpenAI:
    """Wrap an AsyncOpenAI client to automatically trace API calls.

    Usage:
        from openai import AsyncOpenAI
        import glassbox as gb

        client = AsyncOpenAI()
        traced_client = gb.wrap_async_openai(client)

        # Now all calls are automatically traced
        response = await traced_client.chat.completions.create(...)
    """
    return TracedAsyncOpenAI(client, glassbox_client, trace_name)


# Convenience function for direct OpenAI module patching (optional)
def patch_openai(glassbox_client: Optional[GlassboxClient] = None) -> None:
    """Patch the OpenAI module globally to auto-trace all calls.

    This modifies the openai.OpenAI and openai.AsyncOpenAI classes.
    Use with caution - prefer wrap_openai() for more control.

    Usage:
        import glassbox as gb
        gb.patch_openai()

        from openai import OpenAI
        client = OpenAI()  # Automatically traced
    """
    try:
        import openai

        original_openai_init = openai.OpenAI.__init__
        original_async_openai_init = openai.AsyncOpenAI.__init__

        @functools.wraps(original_openai_init)
        def traced_openai_init(self, *args, **kwargs):
            original_openai_init(self, *args, **kwargs)
            # Wrap the client after initialization
            wrapped = TracedOpenAI(self, glassbox_client)
            # Replace methods
            self.chat.completions.create = wrapped.chat_completions_create
            if hasattr(self, "completions"):
                self.completions.create = wrapped.completions_create
            if hasattr(self, "embeddings"):
                self.embeddings.create = wrapped.embeddings_create
            if hasattr(self, "beta") and hasattr(self.beta, "chat"):
                self.beta.chat.completions.parse = wrapped.beta_chat_completions_parse

        @functools.wraps(original_async_openai_init)
        def traced_async_openai_init(self, *args, **kwargs):
            original_async_openai_init(self, *args, **kwargs)
            wrapped = TracedAsyncOpenAI(self, glassbox_client)
            self.chat.completions.create = wrapped.chat_completions_create
            if hasattr(self, "completions"):
                self.completions.create = wrapped.completions_create
            if hasattr(self, "embeddings"):
                self.embeddings.create = wrapped.embeddings_create

        openai.OpenAI.__init__ = traced_openai_init
        openai.AsyncOpenAI.__init__ = traced_async_openai_init

        logger.info("OpenAI module patched for automatic tracing")

    except ImportError:
        logger.warning("OpenAI not installed, skipping patch")
    except Exception as e:
        logger.error(f"Failed to patch OpenAI: {e}")


__all__ = [
    "TracedOpenAI",
    "TracedAsyncOpenAI",
    "wrap_openai",
    "wrap_async_openai",
    "patch_openai",
]