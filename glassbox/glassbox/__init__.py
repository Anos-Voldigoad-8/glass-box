"""
GLASS BOX SDK - Local-first agent observability SDK.

Usage:
    import glassbox as gb

    with gb.trace("agent.workflow"):
        result = my_agent_function()

    @gb.trace
    def my_agent_function():
        return do_something()
"""

from .client import GlassboxClient, configure, get_client
from .context import get_current_span, get_current_trace, set_current_span, set_current_trace
from .tracer import (
    trace,
    step,
    trace_decorator,
    capture_llm_call,
    log,
)
from .types import (
    SpanType,
    SpanStatus,
    TraceStatus,
    TokenUsage,
    Trace,
    Span,
    Trace as TraceType,
    Span as SpanTypeAlias,
)

__version__ = "0.1.0"
__author__ = "GLASS BOX Team"
__email__ = "team@glassbox.dev"

# Main API exports
__all__ = [
    # Client
    "GlassboxClient",
    "configure",
    "get_client",
    
    # Context
    "get_current_span",
    "get_current_trace",
    "set_current_span",
    "set_current_trace",
    
    # Tracing decorators and context managers
    "trace",
    "step",
    "trace_decorator",
    "capture_llm_call",
    "log",
    
    # Types
    "SpanType",
    "SpanStatus", 
    "TraceStatus",
    "TokenUsage",
    "Trace",
    "Span",
    
    # Aliases for backward compatibility
    "TraceType",
    "SpanTypeAlias",
]