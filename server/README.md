# GLASS BOX Backend

FastAPI backend for the GLASS BOX agent observability platform.

## Features

- REST API for ingesting and querying trace data
- WebSocket endpoint for live trace updates
- SQLite storage for local-first data persistence
- Automatic trace broadcasting to connected clients
- CORS enabled for frontend integration

## API Endpoints

### POST `/ingest`
Ingest a trace from the GLASS BOX SDK.

### GET `/sessions`
List all traces/sessions.

### GET `/sessions/{trace_id}`
Get a specific trace by ID.

### WS `/live`
WebSocket endpoint for live trace updates.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python -m server.main
   ```
   or
   ```bash
   uvicorn server.main:app --reload
   ```

3. The server will be available at http://localhost:8000

## Data Model

The backend stores traces and spans in SQLite database with the following schema:

### Traces Table
- id (TEXT, PRIMARY KEY)
- name (TEXT)
- agent_name (TEXT)
- status (TEXT)
- start_time (TEXT)
- end_time (TEXT)
- duration_ms (REAL)
- metadata (TEXT)

### Spans Table
- id (TEXT, PRIMARY KEY)
- trace_id (TEXT, FOREIGN KEY)
- parent_id (TEXT)
- name (TEXT)
- span_type (TEXT)
- status (TEXT)
- start_time (TEXT)
- end_time (TEXT)
- duration_ms (REAL)
- metadata (TEXT)
- token_usage (TEXT)

## Development

To run with auto-reload during development:
```bash
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```