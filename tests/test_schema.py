"""Pytest smoke tests for GLASS BOX schema and API."""

import pytest
import json
import sqlite3
import tempfile
import os
from datetime import datetime

# Test imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'glassbox'))

from glassbox.types import (
    Span, Trace, SpanType, SpanStatus, TraceStatus, TokenUsage, LogEvent, ToolCall,
    calculate_cost, extract_token_usage
)
from glassbox.pricing import (
    load_pricing, get_model_pricing, calculate_cost as dynamic_calculate_cost,
    update_token_usage_cost, normalize_provider, get_all_pricing
)


class TestTypesSchema:
    """Tests for type definitions and schema."""
    
    def test_span_creation(self):
        """Test basic Span creation and serialization."""
        span = Span(
            id="test-span-1",
            trace_id="test-trace-1",
            name="test_span",
            span_type=SpanType.TOOL_CALL,
        )
        
        assert span.id == "test-span-1"
        assert span.trace_id == "test-trace-1"
        assert span.name == "test_span"
        assert span.span_type == SpanType.TOOL_CALL
        assert span.status == SpanStatus.RUNNING
        assert span.duration_ms == 0
    
    def test_span_to_dict(self):
        """Test Span serialization to dict."""
        span = Span(
            id="test-span-1",
            trace_id="test-trace-1",
            name="test_span",
            span_type=SpanType.LLM_CALL,
            status=SpanStatus.SUCCESS,
            duration_ms=100.5,
            metadata={"key": "value"},
        )
        span.finish(SpanStatus.SUCCESS)
        
        data = span.to_dict()
        
        assert data["id"] == "test-span-1"
        assert data["trace_id"] == "test-trace-1"
        assert data["name"] == "test_span"
        assert data["span_type"] == "llm_call"
        assert data["status"] == "success"
        assert data["duration_ms"] == 100.5
        assert data["metadata"] == {"key": "value"}
        assert data["end_time"] is not None
        assert "start_time" in data
    
    def test_span_with_token_usage(self):
        """Test Span with token usage."""
        span = Span(
            id="test-span-1",
            trace_id="test-trace-1",
            name="llm_call",
            span_type=SpanType.LLM_CALL,
        )
        
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            model="gpt-4o",
        )
        span.add_token_usage(usage)
        
        data = span.to_dict()
        
        assert data["token_usage"] is not None
        assert data["token_usage"]["prompt_tokens"] == 100
        assert data["token_usage"]["completion_tokens"] == 50
        assert data["token_usage"]["total_tokens"] == 150
        assert data["token_usage"]["cost_usd"] == 0.001
        assert data["token_usage"]["model"] == "gpt-4o"
    
    def test_span_with_logs(self):
        """Test Span with log events."""
        span = Span(
            id="test-span-1",
            trace_id="test-trace-1",
            name="test_span",
        )
        
        span.log("Test message", level="info", data={"key": "value"})
        span.log("Error message", level="error")
        
        data = span.to_dict()
        
        assert len(data["logs"]) == 2
        assert data["logs"][0]["message"] == "Test message"
        assert data["logs"][0]["level"] == "info"
        assert data["logs"][0]["data"] == {"key": "value"}
        assert data["logs"][1]["message"] == "Error message"
        assert data["logs"][1]["level"] == "error"
    
    def test_span_with_tool_calls(self):
        """Test Span with tool calls."""
        span = Span(
            id="test-span-1",
            trace_id="test-trace-1",
            name="tool_call",
            span_type=SpanType.TOOL_CALL,
        )
        
        tool_call = ToolCall(
            name="search_web",
            arguments={"query": "test"},
            result={"results": ["a", "b"]},
            duration_ms=50.0,
        )
        span.add_tool_call(tool_call)
        
        data = span.to_dict()
        
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "search_web"
        assert data["tool_calls"][0]["arguments"] == {"query": "test"}
        assert data["tool_calls"][0]["result"] == {"results": ["a", "b"]}
        assert data["tool_calls"][0]["duration_ms"] == 50.0
    
    def test_trace_creation(self):
        """Test basic Trace creation."""
        trace = Trace(
            id="test-trace-1",
            name="test_workflow",
            agent_name="test-agent",
        )
        
        assert trace.id == "test-trace-1"
        assert trace.name == "test_workflow"
        assert trace.agent_name == "test-agent"
        assert trace.status == TraceStatus.RUNNING
        assert len(trace.spans) == 0
    
    def test_trace_add_span(self):
        """Test adding spans to trace."""
        trace = Trace(id="test-trace-1", name="test")
        span = Span(id="span-1", trace_id="test-trace-1", name="span1")
        span2 = Span(id="span-2", trace_id="test-trace-1", name="span2", parent_id="span-1")
        
        trace.add_span(span)
        trace.add_span(span2)
        
        assert len(trace.spans) == 2
        assert trace.root_span_id == "span-1"
        assert trace.get_root_span().id == "span-1"
        assert len(trace.get_child_spans("span-1")) == 1
        assert trace.get_child_spans("span-1")[0].id == "span-2"
    
    def test_trace_finish(self):
        """Test finishing a trace."""
        trace = Trace(id="test-trace-1", name="test")
        trace.finish(TraceStatus.SUCCESS)
        
        assert trace.status == TraceStatus.SUCCESS
        assert trace.end_time is not None
        assert trace.duration_ms > 0
    
    def test_token_usage_properties(self):
        """Test TokenUsage properties."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        
        assert usage.tokens_in == 100
        assert usage.tokens_out == 50


class TestLegacyPricing:
    """Tests for legacy pricing (backward compatibility)."""
    
    def test_calculate_cost_gpt4(self):
        """Test cost calculation for GPT-4."""
        cost = calculate_cost("gpt-4", 1000, 500)
        # gpt-4: input $0.03/1k, output $0.06/1k
        # 1000 * 0.03/1000 + 500 * 0.06/1000 = 0.03 + 0.03 = 0.06
        assert abs(cost - 0.06) < 0.001
    
    def test_calculate_cost_gpt35(self):
        """Test cost calculation for GPT-3.5."""
        cost = calculate_cost("gpt-3.5-turbo", 1000, 1000)
        # gpt-3.5-turbo: input $0.0005/1k, output $0.0015/1k
        assert abs(cost - 0.002) < 0.001
    
    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model (should be 0)."""
        cost = calculate_cost("unknown-model-xyz", 1000, 1000)
        assert cost == 0.0


class TestDynamicPricing:
    """Tests for dynamic pricing from YAML."""
    
    def test_load_pricing(self):
        """Test loading pricing from YAML file."""
        pricing = load_pricing()
        assert isinstance(pricing, dict)
        assert len(pricing) > 0
        # Check some known models exist
        assert "openai:gpt-4o" in pricing
        assert "anthropic:claude-3-5-sonnet-20241022" in pricing
    
    def test_get_model_pricing(self):
        """Test getting pricing for specific model."""
        pricing = get_model_pricing("openai", "gpt-4o")
        assert pricing is not None
        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] == 5.00  # $5/M tokens
        assert pricing["output"] == 15.00  # $15/M tokens
    
    def test_get_model_pricing_case_insensitive(self):
        """Test case-insensitive model lookup."""
        pricing1 = get_model_pricing("openai", "GPT-4O")
        pricing2 = get_model_pricing("openai", "gpt-4o")
        assert pricing1 == pricing2
    
    def test_get_model_pricing_normalized_provider(self):
        """Test provider normalization."""
        pricing1 = get_model_pricing("azure", "gpt-4o")
        pricing2 = get_model_pricing("openai", "gpt-4o")
        assert pricing1 == pricing2
    
    def test_dynamic_calculate_cost(self):
        """Test dynamic cost calculation."""
        cost = dynamic_calculate_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
        # gpt-4o: $5/M input, $15/M output
        # 1M * $5/M + 1M * $15/M = $20
        assert abs(cost - 20.0) < 0.01
    
    def test_dynamic_calculate_cost_small_amounts(self):
        """Test dynamic cost calculation with small token counts."""
        cost = dynamic_calculate_cost("openai", "gpt-4o", 1000, 500)
        # 1000 * 5/1M + 500 * 15/1M = 0.005 + 0.0075 = 0.0125
        assert abs(cost - 0.0125) < 0.0001
    
    def test_update_token_usage_cost(self):
        """Test updating TokenUsage with calculated cost."""
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000, model="gpt-4o")
        update_token_usage_cost(usage, "openai", "gpt-4o")
        
        assert usage.cost_usd > 0
        assert abs(usage.cost_usd - 20.0) < 0.01
    
    def test_get_all_pricing(self):
        """Test getting all pricing data."""
        all_pricing = get_all_pricing()
        assert isinstance(all_pricing, dict)
        assert len(all_pricing) > 10  # Should have many models
    
    def test_normalize_provider(self):
        """Test provider normalization."""
        assert normalize_provider("openai") == "openai"
        assert normalize_provider("azure") == "openai"
        assert normalize_provider("anthropic") == "anthropic"
        assert normalize_provider("vertex") == "google"
        assert normalize_provider("local") == "ollama"
        assert normalize_provider("unknown") == "unknown"


class TestExtractTokenUsage:
    """Tests for token usage extraction from provider responses."""
    
    def test_extract_openai_usage(self):
        """Test extracting token usage from OpenAI response."""
        class MockUsage:
            prompt_tokens = 100
            completion_tokens = 50
            total_tokens = 150
        
        class MockResponse:
            usage = MockUsage()
            model = "gpt-4o"
        
        usage = extract_token_usage(MockResponse(), "openai")
        
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "gpt-4o"
    
    def test_extract_anthropic_usage(self):
        """Test extracting token usage from Anthropic response."""
        class MockUsage:
            input_tokens = 100
            output_tokens = 50
        
        class MockResponse:
            usage = MockUsage()
            model = "claude-3-5-sonnet"
        
        usage = extract_token_usage(MockResponse(), "anthropic")
        
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "claude-3-5-sonnet"
    
    def test_extract_ollama_usage(self):
        """Test extracting token usage from Ollama response."""
        class MockResponse:
            prompt_eval_count = 100
            eval_count = 50
            model = "llama3"
        
        usage = extract_token_usage(MockResponse(), "ollama")
        
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "llama3"
    
    def test_extract_dict_usage(self):
        """Test extracting token usage from dict response."""
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            "model": "gpt-4",
        }
        
        usage = extract_token_usage(response, "openai")
        
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "gpt-4"


class TestEnums:
    """Tests for enum values."""
    
    def test_span_type_values(self):
        """Test SpanType enum values."""
        assert SpanType.LLM_CALL.value == "llm_call"
        assert SpanType.TOOL_CALL.value == "tool_call"
        assert SpanType.REASONING.value == "reasoning"
        assert SpanType.ERROR.value == "error"
        assert SpanType.AGENT_STEP.value == "agent_step"
        assert SpanType.CUSTOM.value == "custom"
    
    def test_span_status_values(self):
        """Test SpanStatus enum values."""
        assert SpanStatus.RUNNING.value == "running"
        assert SpanStatus.SUCCESS.value == "success"
        assert SpanStatus.ERROR.value == "error"
        assert SpanStatus.CANCELLED.value == "cancelled"
    
    def test_trace_status_values(self):
        """Test TraceStatus enum values."""
        assert TraceStatus.RUNNING.value == "running"
        assert TraceStatus.SUCCESS.value == "success"
        assert TraceStatus.ERROR.value == "error"
        assert TraceStatus.CANCELLED.value == "cancelled"


class TestDatabaseSchema:
    """Tests for database schema compatibility."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables (matching server schema)
        cursor.execute("""
            CREATE TABLE traces (
                id TEXT PRIMARY KEY,
                name TEXT,
                agent_name TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms REAL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE spans (
                id TEXT PRIMARY KEY,
                trace_id TEXT,
                parent_id TEXT,
                name TEXT,
                span_type TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms REAL,
                metadata TEXT,
                token_usage TEXT,
                logs TEXT,
                FOREIGN KEY (trace_id) REFERENCES traces (id)
            )
        """)
        
        conn.commit()
        yield conn
        
        conn.close()
        os.unlink(db_path)
    
    def test_insert_trace_and_spans(self, temp_db):
        """Test inserting trace and spans into database."""
        cursor = temp_db.cursor()
        
        trace_id = "test-trace-1"
        span_id = "test-span-1"
        
        cursor.execute("""
            INSERT INTO traces (id, name, agent_name, status, start_time, end_time, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id, "test", "test-agent", "success",
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 100.0,
            json.dumps({"test": "metadata"})
        ))
        
        cursor.execute("""
            INSERT INTO spans (id, trace_id, parent_id, name, span_type, status, start_time, end_time, duration_ms, metadata, token_usage, logs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            span_id, trace_id, None, "test_span", "tool_call", "success",
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 50.0,
            json.dumps({}), json.dumps({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost_usd": 0.001, "model": "gpt-4o"}),
            json.dumps([{"timestamp": datetime.utcnow().isoformat(), "level": "info", "message": "test"}])
        ))
        
        temp_db.commit()
        
        # Verify
        cursor.execute("SELECT * FROM traces WHERE id = ?", (trace_id,))
        trace_row = cursor.fetchone()
        assert trace_row is not None
        assert trace_row[1] == "test"  # name
        
        cursor.execute("SELECT * FROM spans WHERE id = ?", (span_id,))
        span_row = cursor.fetchone()
        assert span_row is not None
        assert span_row[3] == "test_span"  # name
        assert span_row[4] == "tool_call"  # span_type
    
    def test_span_logs_column_exists(self, temp_db):
        """Test that spans table has logs column."""
        cursor = temp_db.cursor()
        cursor.execute("PRAGMA table_info(spans)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "logs" in columns
    
    def test_token_usage_storage(self, temp_db):
        """Test token usage is stored correctly."""
        cursor = temp_db.cursor()
        
        trace_id = "test-trace-2"
        span_id = "test-span-2"
        
        cursor.execute("""
            INSERT INTO traces (id, name, agent_name, status, start_time, end_time, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (trace_id, "test", "test-agent", "success",
              datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 100.0, "{}"))
        
        token_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost_usd": 0.001, "model": "gpt-4o"}
        
        cursor.execute("""
            INSERT INTO spans (id, trace_id, parent_id, name, span_type, status, start_time, end_time, duration_ms, metadata, token_usage, logs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (span_id, trace_id, None, "llm_call", "llm_call", "success",
              datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), 50.0,
              "{}", json.dumps(token_usage), "[]"))
        
        temp_db.commit()
        
        cursor.execute("SELECT token_usage FROM spans WHERE id = ?", (span_id,))
        row = cursor.fetchone()
        stored_usage = json.loads(row[0])
        
        assert stored_usage["prompt_tokens"] == 100
        assert stored_usage["completion_tokens"] == 50
        assert stored_usage["total_tokens"] == 150
        assert stored_usage["cost_usd"] == 0.001
        assert stored_usage["model"] == "gpt-4o"


class TestAPIResponseSchema:
    """Tests for API response schema compatibility."""
    
    def test_trace_response_structure(self):
        """Test that TraceResponse has expected structure."""
        from server.server.app import TraceResponse, SpanBase, TokenUsage
        
        token_usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            model="gpt-4o"
        )
        
        span = SpanBase(
            id="span-1",
            trace_id="trace-1",
            parent_id=None,
            name="test_span",
            span_type="tool_call",
            status="success",
            start_time=datetime.utcnow().isoformat(),
            end_time=datetime.utcnow().isoformat(),
            duration_ms=50.0,
            metadata={},
            token_usage=token_usage,
            logs=None,
            children=[]
        )
        
        trace = TraceResponse(
            id="trace-1",
            name="test_trace",
            agent_name="test-agent",
            status="success",
            start_time=datetime.utcnow().isoformat(),
            end_time=datetime.utcnow().isoformat(),
            duration_ms=100.0,
            metadata={},
            spans=[span]
        )
        
        # Verify structure
        assert trace.id == "trace-1"
        assert trace.name == "test_trace"
        assert trace.agent_name == "test-agent"
        assert trace.status == "success"
        assert len(trace.spans) == 1
        assert trace.spans[0].id == "span-1"
        assert trace.spans[0].token_usage is not None
        assert trace.spans[0].token_usage.total_tokens == 150
    
    def test_span_response_with_logs(self):
        """Test SpanBase with logs field."""
        from server.server.app import SpanBase
        
        logs = [
            {"timestamp": datetime.utcnow().isoformat(), "level": "info", "message": "test", "name": "", "data": {}}
        ]
        
        span = SpanBase(
            id="span-1",
            trace_id="trace-1",
            parent_id=None,
            name="test_span",
            span_type="tool_call",
            status="success",
            start_time=datetime.utcnow().isoformat(),
            end_time=datetime.utcnow().isoformat(),
            duration_ms=50.0,
            metadata={},
            token_usage=None,
            logs=logs,
            children=[]
        )
        
        assert span.logs is not None
        assert len(span.logs) == 1
        assert span.logs[0]["message"] == "test"


# Run with: pytest tests/test_schema.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])