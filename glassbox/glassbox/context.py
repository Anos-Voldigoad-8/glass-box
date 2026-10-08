"""Context management for GLASS BOX SDK."""

from __future__ import annotations

import contextvars
from typing import Optional

from .types import Span, Trace

_current_span: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar("_current_span", default=None)
_current_trace: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar("_current_trace", default=None)
_global_client: contextvars.ContextVar[Optional["GlassboxClient"]] = contextvars.ContextVar("_global_client", default=None)


def get_current_span() -> Optional[Span]:
    """Get the currently active span from context."""
    return _current_span.get()


def set_current_span(span: Optional[Span]) -> None:
    """Set the currently active span in context."""
    _current_span.set(span)


def get_current_trace() -> Optional[Trace]:
    """Get the currently active trace from context."""
    return _current_trace.get()


def set_current_trace(trace: Optional[Trace]) -> None:
    """Set the currently active trace in context."""
    _current_trace.set(trace)


def get_global_client() -> Optional["GlassboxClient"]:
    """Get the globally configured Glassbox client."""
    return _global_client.get()


def set_global_client(client: "GlassboxClient") -> None:
    """Set the globally configured Glassbox client."""
    _global_client.set(client)


class trace_context:
    """Context manager for managing trace context."""

    def __init__(self, trace: Trace) -> None:
        self._trace = trace
        self._previous_trace: Optional[Trace] = None

    def __enter__(self) -> Trace:
        self._previous_trace = get_current_trace()
        set_current_trace(self._trace)
        return self._trace

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        set_current_trace(self._previous_trace)


class span_context:
    """Context manager for managing span context."""

    def __init__(self, span: Span) -> None:
        self._span = span
        self._previous_span: Optional[Span] = None

    def __enter__(self) -> Span:
        self._previous_span = get_current_span()
        set_current_span(self._span)
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        set_current_span(self._previous_span)


def configure(
    endpoint: str = "http://localhost:8000",
    api_key: str | None = None,
    batch_size: int = 10,
    flush_interval: float = 1.0,
) -> "GlassboxClient":
    """Configure the global Glassbox client."""
    from .client import GlassboxClient

    client = GlassboxClient(endpoint=endpoint, api_key=api_key, batch_size=batch_size, flush_interval=flush_interval)
    set_global_client(client)
    return client