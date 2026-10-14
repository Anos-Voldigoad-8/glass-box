"""Type definitions for GLASS BOX SDK."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SpanType(str, Enum):
    """Types of spans in a trace."""

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"
    ERROR = "error"
    AGENT_STEP = "agent_step"
    CUSTOM = "custom"


class SpanStatus(str, Enum):
    """Status of a span."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class TraceStatus(str, Enum):
    """Status of a trace."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class TokenUsage:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""

    @property
    def tokens_in(self) -> int:
        return self.prompt_tokens

    @property
    def tokens_out(self) -> int:
        return self.completion_tokens


@dataclass
class LogEvent:
    """A log event within a span."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: str = "info"
    message: str = ""
    name: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class ToolCall:
    """A tool/function call."""

    name: str
    arguments: dict
    result: Any = None
    error: str | None = None
    duration_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Span:
    """A single span in a trace."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    name: str = ""
    span_type: SpanType = SpanType.CUSTOM
    status: SpanStatus = SpanStatus.RUNNING
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_ms: float = 0
    metadata: dict = field(default_factory=dict)
    logs: list[LogEvent] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    token_usage: TokenUsage | None = None

    def add_log(self, message: str, level: str = "info", data: dict | None = None, name: str = "") -> LogEvent:
        """Add a log event to this span."""
        event = LogEvent(message=message, level=level, data=data or {}, name=name)
        self.logs.append(event)
        return event

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call to this span."""
        self.tool_calls.append(tool_call)

    def add_token_usage(self, usage: TokenUsage) -> None:
        """Add token usage to this span."""
        if self.token_usage is None:
            self.token_usage = usage
        else:
            self.token_usage.prompt_tokens += usage.prompt_tokens
            self.token_usage.completion_tokens += usage.completion_tokens
            self.token_usage.total_tokens += usage.total_tokens

    def log(self, message: str, level: str = "info", data: dict | None = None, name: str = "") -> LogEvent:
        """Add a log event to this span (convenience method)."""
        return self.add_log(message, level, data, name)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.metadata[key] = value

    def finish(self, status: SpanStatus = SpanStatus.SUCCESS, error: str | None = None) -> None:
        """Finish this span."""
        self.end_time = datetime.utcnow()
        self.status = status
        if error:
            self.metadata["error"] = error

    def to_dict(self) -> dict:
        """Convert span to dictionary for serialization."""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "span_type": self.span_type.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "logs": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "name": log.name,
                    "data": log.data,
                }
                for log in self.logs
            ],
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "error": tc.error,
                    "duration_ms": tc.duration_ms,
                    "timestamp": tc.timestamp.isoformat(),
                }
                for tc in self.tool_calls
            ],
            "token_usage": {
                "prompt_tokens": self.token_usage.prompt_tokens if self.token_usage else 0,
                "completion_tokens": self.token_usage.completion_tokens if self.token_usage else 0,
                "total_tokens": self.token_usage.total_tokens if self.token_usage else 0,
                "cost_usd": self.token_usage.cost_usd if self.token_usage else 0.0,
                "model": self.token_usage.model if self.token_usage else "",
            } if self.token_usage else None,
        }


@dataclass
class Trace:
    """A complete trace of an agent execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    agent_name: str = ""
    status: TraceStatus = TraceStatus.RUNNING
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_ms: float = 0
    metadata: dict = field(default_factory=dict)
    spans: dict[str, Span] = field(default_factory=dict)
    root_span_id: str | None = None

    def add_span(self, span: Span) -> None:
        """Add a span to this trace."""
        self.spans[span.id] = span
        if self.root_span_id is None:
            self.root_span_id = span.id

    def get_span(self, span_id: str) -> Span | None:
        """Get a span by ID."""
        return self.spans.get(span_id)

    def get_root_span(self) -> Span | None:
        """Get the root span of this trace."""
        if self.root_span_id:
            return self.spans.get(self.root_span_id)
        return None

    def get_child_spans(self, parent_id: str) -> list[Span]:
        """Get all child spans of a parent span."""
        return [s for s in self.spans.values() if s.parent_id == parent_id]

    def finish(self, status: TraceStatus = TraceStatus.SUCCESS, error: str | None = None) -> None:
        """Finish this trace."""
        self.end_time = datetime.utcnow()
        self.status = status
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        if error:
            self.metadata["error"] = error

    def to_span(self) -> Span:
        """Convert trace to a root span for ingestion."""
        root_span = Span(
            id=self.id,
            trace_id=self.id,
            name=self.name,
            span_type=SpanType.AGENT_STEP,
            status=SpanStatus.SUCCESS if self.status == TraceStatus.SUCCESS else SpanStatus.ERROR,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_ms=self.duration_ms,
            metadata=self.metadata,
        )
        return root_span


# Legacy model cost estimation (kept for backward compatibility)
# Use glassbox.pricing.calculate_cost for dynamic pricing from pricing.yaml
MODEL_COSTS = {
    "gpt4": {"input": 0.03, "output": 0.06},
    "gpt4turbo": {"input": 0.01, "output": 0.03},
    "gpt4o": {"input": 0.005, "output": 0.015},
    "gpt35turbo": {"input": 0.0005, "output": 0.0015},
    "claude3opus": {"input": 0.015, "output": 0.075},
    "claude3sonnet": {"input": 0.003, "output": 0.015},
    "claude3haiku": {"input": 0.00025, "output": 0.00125},
    "llama370b": {"input": 0.0009, "output": 0.0009},
    "llama38b": {"input": 0.0002, "output": 0.0002},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost for a model call (legacy - uses hardcoded pricing).
    
    For dynamic pricing from pricing.yaml, use glassbox.pricing.calculate_cost instead.
    """
    model_key = model.lower().replace(".", "").replace("-", "")
    costs = MODEL_COSTS.get(model_key, {"input": 0, "output": 0})
    return (prompt_tokens * costs["input"] / 1000) + (completion_tokens * costs["output"] / 1000)


def extract_token_usage(response: Any, provider: str = "openai") -> TokenUsage | None:
    """Extract token usage from various provider response formats."""
    # Handle dict responses first (most explicit)
    if isinstance(response, dict):
        if "usage" in response and response["usage"] is not None:
            usage = response["usage"]
            if provider == "anthropic" or "input_tokens" in usage:
                # Anthropic format
                return TokenUsage(
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    model=response.get("model", ""),
                )
            else:
                # OpenAI format
                return TokenUsage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=response.get("model", ""),
                )
        elif "prompt_eval_count" in response:
            # Ollama format
            return TokenUsage(
                prompt_tokens=response.get("prompt_eval_count", 0),
                completion_tokens=response.get("eval_count", 0),
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                model=response.get("model", ""),
            )
    
    # Handle object responses
    if hasattr(response, "usage") and response.usage is not None:
        usage = response.usage
        
        if provider == "anthropic" or (hasattr(usage, "input_tokens") and hasattr(usage, "output_tokens")):
            # Anthropic format
            return TokenUsage(
                prompt_tokens=getattr(usage, "input_tokens", 0),
                completion_tokens=getattr(usage, "output_tokens", 0),
                total_tokens=getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0),
                model=getattr(response, "model", ""),
            )
        elif hasattr(usage, "prompt_tokens") or hasattr(usage, "completion_tokens"):
            # OpenAI format
            return TokenUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
                total_tokens=getattr(usage, "total_tokens", 0),
                model=getattr(response, "model", ""),
            )
    
    # Handle Ollama object responses
    if provider == "ollama" and hasattr(response, "prompt_eval_count"):
        return TokenUsage(
            prompt_tokens=getattr(response, "prompt_eval_count", 0),
            completion_tokens=getattr(response, "eval_count", 0),
            total_tokens=getattr(response, "prompt_eval_count", 0) + getattr(response, "eval_count", 0),
            model=getattr(response, "model", ""),
        )
    
    return None