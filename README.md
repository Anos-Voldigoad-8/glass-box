# GLASS BOX - Local-First Agent Observability Platform

A comprehensive observability platform for monitoring, debugging, and understanding AI agent systems. Built with a local-first approach, GLASS BOX provides deep visibility into LLM calls, tool usage, reasoning steps, and agent workflows.

## 🎯 Overview

GLASS BOX consists of four main components:

1. **SDK** (`glassbox/`) - Python library for instrumenting AI agents
2. **Backend** (`server/`) - FastAPI server with SQLite storage for trace data
3. **Dashboard** (`dashboard/`) - Cyberpunk/terminal-themed observability UI
4. **Example** (`example_agent.py`) - Demonstration multi-agent system

## 🚀 Quick Start (2 Minutes)

### 1. Install Dependencies
```bash
# Install SDK
cd glassbox
pip install -e .

# Install backend dependencies  
cd ../server
pip install -r requirements.txt
```

### 2. Start the Backend
```bash
# In the server directory
python -m server.app
# or
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

### 3. Run the Example Agent
```bash
# In the project root
python example_agent.py
```

### 4. Open the Dashboard
Open your browser to: http://localhost:8000/dashboard/

## 📦 Components Explained

### SDK (`glassbox/`)
The core instrumentation library that captures traces from your AI agents.

**Key Features:**
- Zero-configuration local storage
- Automatic LLM token usage tracking
- Decorator and context manager APIs
- Real-time WebSocket streaming to backend
- Framework agnostic (works with any Python code)

**Usage:**
```python
import glassbox as gb

# Configure (optional - defaults to localhost:8000)
gb.configure(endpoint="http://localhost:8000")

# Trace functions
@gb.trace
def my_agent_function():
    result = some_llm_call()
    return result

# Context managers
with gb.trace("workflow-name"):
    with gb.step("tool-call"):
        result = my_tool()
    
    # Automatic LLM token tracking
    response = openai.chat.completions.create(...)
    gb.capture_llm_call("gpt-4", messages, response)
```

### Backend (`server/`)
FastAPI server that receives, stores, and serves trace data.

**Endpoints:**
- `POST /ingest` - Receive traces from SDK
- `GET /sessions` - List all traces
- `GET /sessions/{id}` - Get specific trace
- `WS /live` - WebSocket for real-time updates
- `GET /health` - Health check

**Technology:**
- FastAPI for high-performance API
- SQLite for local-first storage
- WebSocket for real-time dashboard updates
- Automatic trace broadcasting

### Dashboard (`dashboard/`)
Cyberpunk/terminal-themed observability interface.

**Features:**
- Real-time trace updates via WebSocket
- Session list with filtering and search
- Trace visualization (tree, timeline, logs views)
- Live metrics (token usage, cost, latency, errors)
- Replay mode for stepping through execution
- Diff mode for comparing traces
- Terminal aesthetic with neon accents

### Example Agent (`example_agent.py`)
Complete demonstration of a 3-agent system:
1. **Research Agent** - Gathers information on a topic
2. **Writing Agent** - Creates content from research
3. **Editor Agent** - Reviews and improves the content

Each agent is fully instrumented with GLASS BOX to show:
- Multi-agent workflow tracing
- LLM call tracking with token usage
- Tool call monitoring
- Reasoning step visualization
- Error handling and performance metrics

## 🏗️ Architecture

```
[Your AI Agent Code] 
          ↓ (SDK)
[GLASS BOX SDK] ────────────┐
          ↓ HTTP/WebSocket   │
[GLASS BOX Backend]         │
          ↓                  │
[SQLite Database] ◄─────────┘
          ↑
[GLASS BOX Dashboard] ← WebSocket Updates
```

## 🔧 Configuration

### SDK Configuration
```python
gb.configure(
    endpoint="http://your-server:8000",  # Default: localhost:8000
    api_key="your-api-key",              # Optional for auth
    batch_size=10,                       # Send in batches of 10
    flush_interval=1.0                   # Flush every 1 second
)
```

### Backend Configuration
Modify `server/app.py` to change:
- Database location (currently `glassbox.db`)
- CORS origins (currently allows all)
- Host/port binding

## 📊 Data Model

### Trace
- `id`: Unique identifier
- `name`: Trace name
- `agent_name`: Name of the agent
- `status`: running/success/error/cancelled
- `timestamps`: start_time, end_time, duration_ms
- `metadata`: Custom key-value pairs
- `spans`: List of spans in the trace

### Span
- `id`: Unique identifier
- `trace_id`: Parent trace ID
- `parent_id`: Parent span ID (null for root)
- `name`: Span name
- `type`: llm_call/tool_call/reasoning/error/agent_step/custom
- `status`: running/success/error/cancelled
- `timing`: start_time, end_time, duration_ms
- `metadata`: Custom data
- `token_usage`: Token counts and cost
- `logs`: Log events within the span
- `tool_calls`: Tool/function calls

## 🛠️ Development

### Building the SDK
```bash
cd glassbox
python -m build  # Creates dist/glassbox-*.whl
```

### Running Tests
```bash
# SDK tests
cd glassbox
pytest

# Backend tests (when implemented)
cd server
pytest
```

## 🌟 Features

### For Developers
- Zero-instrumentation tracing via decorators
- Context managers for manual control
- Automatic LLM token/cost tracking
- Local-first with optional remote backend
- Minimal performance impact
- Comprehensive debugging information

### For Operators
- Real-time system visibility
- Performance bottleneck identification
- Cost tracking and optimization
- Error tracing and root cause analysis
- Audit trails for compliance
- Experiment comparison (diff mode)

### For Researchers
- Detailed reasoning trace analysis
- Prompt/response inspection
- Token usage optimization
- Comparative study capabilities
- Reproducible experiment tracking

## 📜 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

Built with ❤️ for the AI developer community.
Special thanks to all contributors and early adopters.