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
    capture_llm_call,
    log,
    step,
    trace,
    trace_decorator,
)
from .types import (
    Span,
    SpanStatus,
    SpanType,
    TokenUsage,
    Trace,
    TraceStatus,
)
from .types import (
    Span as SpanTypeAlias,
)
from .types import (
    Trace as TraceType,
)

# Optional integrations
try:
    from .openai import (
        TracedAsyncOpenAI,
        TracedOpenAI,
        patch_openai,
        wrap_async_openai,
        wrap_openai,
    )
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from .anthropic import (
        TracedAnthropic,
        TracedAsyncAnthropic,
        patch_anthropic,
        wrap_anthropic,
        wrap_async_anthropic,
    )
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from .langchain import GlassboxCallbackHandler, get_langchain_callback
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from .pricing import (
    calculate_cost as dynamic_calculate_cost,
)
from .pricing import (
    get_all_pricing,
    get_model_pricing,
    load_pricing,
    normalize_provider,
    reload_pricing,
    update_token_usage_cost,
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
        "TracedAsyncOpenAI",
        "TracedOpenAI",
        "patch_openai",
        "wrap_async_openai",
        "wrap_openai",
    ])

if ANTHROPIC_AVAILABLE:
    __all__.extend([
        "TracedAnthropic",
        "TracedAsyncAnthropic",
        "patch_anthropic",
        "wrap_anthropic",
        "wrap_async_anthropic",
    ])

if LANGCHAIN_AVAILABLE:
    __all__.extend([
        "GlassboxCallbackHandler",
        "get_langchain_callback",
    ])