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

# Optional integrations
try:
    from .openai import TracedOpenAI, TracedAsyncOpenAI, wrap_openai, wrap_async_openai, patch_openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from .anthropic import TracedAnthropic, TracedAsyncAnthropic, wrap_anthropic, wrap_async_anthropic, patch_anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from .langchain import GlassboxCallbackHandler, get_langchain_callback
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from .pricing import (
    load_pricing,
    get_model_pricing,
    calculate_cost as dynamic_calculate_cost,
    update_token_usage_cost,
    get_all_pricing,
    reload_pricing,
    normalize_provider,
)

__version__ = "0.2.0"
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
    
    # Pricing
    "load_pricing",
    "get_model_pricing",
    "dynamic_calculate_cost",
    "update_token_usage_cost",
    "get_all_pricing",
    "reload_pricing",
    "normalize_provider",
]

# Conditional exports for optional integrations
if OPENAI_AVAILABLE:
    __all__.extend([
        "TracedOpenAI",
        "TracedAsyncOpenAI",
        "wrap_openai",
        "wrap_async_openai",
        "patch_openai",
    ])

if ANTHROPIC_AVAILABLE:
    __all__.extend([
        "TracedAnthropic",
        "TracedAsyncAnthropic",
        "wrap_anthropic",
        "wrap_async_anthropic",
        "patch_anthropic",
    ])

if LANGCHAIN_AVAILABLE:
    __all__.extend([
        "GlassboxCallbackHandler",
        "get_langchain_callback",
    ])