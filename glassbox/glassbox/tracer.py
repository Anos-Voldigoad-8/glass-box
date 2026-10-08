"""Decorators and context managers for tracing."""

from __future__ import annotations

import functools
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Optional

from .client import GlassboxClient, get_client
from .context import get_current_span, get_current_trace, set_current_span, set_current_trace
from .types import LogEvent, Span, SpanStatus, SpanType, TokenUsage, Trace, TraceStatus, extract_token_usage, calculate_cost


@contextmanager
def trace(
    name: str,
    agent_name: str = "unknown",
    metadata: dict | None = None,
    client: Optional[GlassboxClient] = None,
):
    """Context manager to create a trace."""
    c = client or get_client()
    trace_obj = Trace(
        id=str(uuid.uuid4()),
        name=name,
        agent_name=agent_name,
        metadata=metadata or {},
    )

    previous_trace = get_current_trace()
    previous_span = get_current_span()

    set_current_trace(trace_obj)
    set_current_span(None)

    try:
        yield trace_obj
    except Exception as e:
        trace_obj.finish(TraceStatus.ERROR, str(e))
        raise
    finally:
        trace_obj.finish()
        c.add_trace(trace_obj)
        set_current_trace(previous_trace)
        set_current_span(previous_span)


@contextmanager
def step_context(
    name: str,
    step_type: SpanType | str = SpanType.TOOL_CALL,
    metadata: dict | None = None,
    client: Optional[GlassboxClient] = None,
):
    """Context manager to create a span/step within a trace."""
    c = client or get_client()

    # Convert string step_type to enum if needed
    if isinstance(step_type, str):
        try:
            step_type = SpanType(step_type)
        except ValueError:
            step_type = SpanType.CUSTOM

    current_trace = get_current_trace()
    current_span = get_current_span()

    # If no active trace, create an implicit one
    if current_trace is None:
        with trace(name="__implicit__", agent_name="unknown", client=c) as trace_obj:
            current_trace = get_current_trace()
            current_span = get_current_span()
            if current_trace is None:
                raise RuntimeError("Failed to create implicit trace")

    span = Span(
        id=str(uuid.uuid4()),
        trace_id=current_trace.id if current_trace else str(uuid.uuid4()),
        parent_id=current_span.id if current_span else None,
        name=name,
        span_type=step_type,
        metadata=metadata or {},
    )

    if current_trace:
        current_trace.add_span(span)

    set_current_span(span)

    start_time = time.perf_counter()
    error = None

    try:
        yield span
    except Exception as e:
        error = e
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if span:
            if error:
                span.finish(SpanStatus.ERROR, str(error))
            else:
                span.finish(SpanStatus.SUCCESS)
            span.duration_ms = duration_ms
            # Span is already added to trace via current_trace.add_span(span) above
            # The trace will be sent as a whole when the trace context exits
        set_current_span(current_span)


def trace_decorator(
    name: str | None = None,
    step_type: SpanType = SpanType.TOOL_CALL,
    agent_name: str | None = None,
):
    """Decorator to trace a function."""
    def decorator(func: Callable) -> Callable:
        trace_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with trace(trace_name, agent_name=agent_name or "unknown") as trace_obj:
                trace_obj.metadata["function"] = func.__name__
                trace_obj.metadata["module"] = func.__module__
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    trace_obj.metadata["result_type"] = type(result).__name__
                    return result
                except Exception as e:
                    raise
                finally:
                    trace_obj.metadata["duration_ms"] = (time.perf_counter() - start_time) * 1000

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with trace(trace_name, agent_name=agent_name or "unknown") as trace_obj:
                trace_obj.metadata["function"] = func.__name__
                trace_obj.metadata["module"] = func.__module__
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    trace_obj.metadata["result_type"] = type(result).__name__
                    return result
                except Exception as e:
                    raise
                finally:
                    trace_obj.metadata["duration_ms"] = (time.perf_counter() - start_time) * 1000

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


def step_decorator(
    name: str | None = None,
    step_type: SpanType = SpanType.TOOL_CALL,
):
    """Decorator to trace a function as a step."""
    def decorator(func: Callable) -> Callable:
        step_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with step_context(step_name, step_type=step_type) as span_obj:
                span_obj.metadata["function"] = func.__name__
                span_obj.metadata["module"] = func.__module__
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    span_obj.metadata["result_type"] = type(result).__name__
                    return result
                except Exception as e:
                    raise
                finally:
                    span_obj.metadata["duration_ms"] = (time.perf_counter() - start_time) * 1000

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with step_context(step_name, step_type=step_type) as span_obj:
                span_obj.metadata["function"] = func.__name__
                span_obj.metadata["module"] = func.__module__
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    span_obj.metadata["result_type"] = type(result).__name__
                    return result
                except Exception as e:
                    raise
                finally:
                    span_obj.metadata["duration_ms"] = (time.perf_counter() - start_time) * 1000

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


def capture_llm_call(
    model: str,
    messages: list[dict],
    response: Any,
    provider: str = "openai",
    client: Optional[GlassboxClient] = None,
) -> Span:
    """Capture an LLM call from a response object."""
    c = client or get_client()
    return c.capture_llm_call(model, messages, response, provider)


def step(
    name: str,
    step_type: SpanType = SpanType.TOOL_CALL,
    metadata: dict | None = None,
):
    """Step context manager - returns a context manager for creating spans."""
    return step_context(name, step_type, metadata)


def log(
    message: str,
    level: str = "info",
    data: dict | None = None,
    name: str = "",
) -> LogEvent | None:
    """Log a message to the current active span."""
    current_span = get_current_span()
    if current_span:
        return current_span.log(message, level, data, name)
    return None


__all__ = [
    "trace",
    "step",
    "trace_decorator",
    "step_decorator",
    "capture_llm_call",
    "log",
    "SpanContextManager",
]