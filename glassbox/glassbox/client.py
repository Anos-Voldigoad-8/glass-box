"""Client for sending traces to GLASS BOX backend."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from typing import Any, Optional

import httpx

from .types import Span, SpanType, SpanStatus, TokenUsage, Trace, extract_token_usage
from .pricing import calculate_cost as dynamic_calculate_cost, normalize_provider

logger = logging.getLogger(__name__)


class GlassboxClient:
    """Client for sending traces to GLASS BOX backend."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8000",
        api_key: str | None = None,
        batch_size: int = 10,
        flush_interval: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._logger = logger or logging.getLogger(__name__)

        self._buffer: deque[Span] = deque()
        self._lock = threading.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        return self._client

    def add_span(self, span: Span) -> None:
        """Add a span to the buffer."""
        with self._lock:
            self._buffer.append(span)
            if len(self._buffer) >= self.batch_size:
                self._flush_sync()

    def _flush_sync(self) -> None:
        """Flush buffer synchronously (for batch size threshold)."""
        if not self._buffer:
            return

        spans = list(self._buffer)
        self._buffer.clear()

        try:
            client = httpx.Client(timeout=10.0)
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            for span in spans:
                data = span.to_dict()
                client.post(f"{self.endpoint}/ingest", json=data, headers=headers)
            client.close()
        except Exception as e:
            self._logger.error("Sync flush failed", exc_info=e)

    async def _flush_async(self) -> None:
        """Flush buffer asynchronously."""
        async with self._lock:
            if not self._buffer:
                return

            spans = list(self._buffer)
            self._buffer.clear()

        if not spans:
            return

        try:
            client = await self._get_client()
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            for span in spans:
                data = span.to_dict()
                await client.post(f"{self.endpoint}/ingest", json=data, headers=headers)
        except Exception as e:
            self._logger.error("Async flush failed", exc_info=e)

    async def _periodic_flush(self) -> None:
        """Periodically flush the buffer."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            await self._flush_async()

    def start(self) -> None:
        """Start the background flush task."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(self._periodic_flush())
        except RuntimeError:
            pass  # No event loop running

    def stop(self) -> None:
        """Stop the background flush task and flush remaining spans."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        self._flush_sync()

    def capture_llm_call(
        self,
        model: str,
        messages: list[dict],
        response: Any,
        provider: str = "openai",
    ) -> Span:
        """Capture an LLM call from a response object."""
        usage = extract_token_usage(response, provider)
        cost = 0.0
        if usage:
            # Use dynamic pricing with provider normalization
            normalized_provider = normalize_provider(provider)
            cost = dynamic_calculate_cost(normalized_provider, model, usage.prompt_tokens, usage.completion_tokens)
            usage.cost_usd = cost

        from .context import get_current_trace, get_current_span

        current_trace = get_current_trace()
        current_span = get_current_span()

        span = Span(
            id=str(uuid.uuid4()),
            trace_id=current_trace.id if current_trace else str(uuid.uuid4()),
            parent_id=current_span.id if current_span else None,
            name=f"llm_call:{model}",
            span_type=SpanType.LLM_CALL,
            metadata={
                "model": model,
                "provider": provider,
                "messages": messages,
                "response": str(response)[:1000],  # Truncate
                "cost_usd": cost,
            },
        )

        if usage:
            span.add_token_usage(usage)

        span.finish(SpanStatus.SUCCESS)

        if current_trace:
            current_trace.add_span(span)
        else:
            self.add_span(span)
        return span

    def flush(self) -> None:
        """Flush all buffered spans."""
        self._flush_sync()

    def add_trace(self, trace: Trace) -> None:
        """Send a complete trace with all spans to the backend."""
        try:
            client = httpx.Client(timeout=10.0)
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Convert trace to the format expected by the server
            trace_data = {
                "id": trace.id,
                "name": trace.name,
                "agent_name": trace.agent_name,
                "status": trace.status.value if hasattr(trace.status, 'value') else trace.status,
                "start_time": trace.start_time.isoformat() if trace.start_time else None,
                "end_time": trace.end_time.isoformat() if trace.end_time else None,
                "duration_ms": trace.duration_ms,
                "metadata": trace.metadata,
                "spans": [span.to_dict() for span in trace.spans.values()]
            }

            client.post(f"{self.endpoint}/ingest", json=trace_data, headers=headers)
            client.close()
        except Exception as e:
            self._logger.error("Failed to send trace", exc_info=e)

    async def aclose(self) -> None:
        """Close the client and flush."""
        self.stop()
        await self._flush_async()
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_global_client: Optional[GlassboxClient] = None


def get_client() -> GlassboxClient:
    """Get the global client instance."""
    global _global_client
    if _global_client is None:
        _global_client = GlassboxClient()
    return _global_client


def configure(
    endpoint: str = "http://localhost:8000",
    api_key: str | None = None,
    batch_size: int = 10,
    flush_interval: float = 1.0,
) -> GlassboxClient:
    """Configure the global client."""
    global _global_client
    _global_client = GlassboxClient(endpoint=endpoint, api_key=api_key, batch_size=batch_size, flush_interval=flush_interval)
    _global_client.start()
    return _global_client


def shutdown() -> None:
    """Shutdown the global client."""
    global _global_client
    if _global_client:
        _global_client.stop()
        _global_client = None