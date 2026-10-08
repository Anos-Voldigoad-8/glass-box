"""
GLASS BOX Backend - FastAPI Application
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import json
import uuid
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager
import os

# Database setup
DATABASE_URL = "glassbox.db"

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Traces table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traces (
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
    
    # Spans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spans (
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
            FOREIGN KEY (trace_id) REFERENCES traces (id)
        )
    """)
    
    # Indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_spans_parent_id ON spans(parent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time)")
    
    conn.commit()
    conn.close()

# Pydantic models for API
class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""

class SpanBase(BaseModel):
    id: str
    trace_id: str
    parent_id: Optional[str] = None
    name: str
    span_type: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: float
    metadata: Dict[str, Any] = {}
    token_usage: Optional[TokenUsage] = None

class SpanCreate(SpanBase):
    pass

class TraceBase(BaseModel):
    id: str
    name: str
    agent_name: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: float
    metadata: Dict[str, Any] = {}

class TraceCreate(TraceBase):
    spans: List[SpanCreate] = []

class TraceResponse(TraceBase):
    spans: List[SpanBase] = []

class MetricsUpdate(BaseModel):
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency: float = 0.0
    error_count: int = 0

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except:
            # Remove broken connection
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except:
                # Remove broken connection
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

manager = ConnectionManager()

# Database dependency
def get_db():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # To get dict-like rows
    try:
        yield conn
    finally:
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    pass

# Create FastAPI app
app = FastAPI(
    title="GLASS BOX API",
    description="Backend for GLASS BOX agent observability platform",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dashboard static files
dashboard_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dashboard")
app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")

# Helper functions
def row_to_trace(row) -> TraceResponse:
    """Convert database row to TraceResponse."""
    trace_id = row['id']
    
    # Get spans for this trace
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time", (trace_id,))
    span_rows = cursor.fetchall()
    conn.close()
    
    spans = []
    for span_row in span_rows:
        spans.append(SpanBase(
            id=span_row['id'],
            trace_id=span_row['trace_id'],
            parent_id=span_row['parent_id'],
            name=span_row['name'],
            span_type=span_row['span_type'],
            status=span_row['status'],
            start_time=span_row['start_time'],
            end_time=span_row['end_time'],
            duration_ms=span_row['duration_ms'],
            metadata=json.loads(span_row['metadata']) if span_row['metadata'] else {},
            token_usage=json.loads(span_row['token_usage']) if span_row['token_usage'] else None
        ))
    
    return TraceResponse(
        id=row['id'],
        name=row['name'],
        agent_name=row['agent_name'],
        status=row['status'],
        start_time=row['start_time'],
        end_time=row['end_time'],
        duration_ms=row['duration_ms'],
        metadata=json.loads(row['metadata']) if row['metadata'] else {},
        spans=spans
    )

# Routes
@app.post("/ingest")
async def ingest_trace(trace: TraceCreate, db: sqlite3.Connection = Depends(get_db)):
    """Ingest a trace from the SDK."""
    cursor = db.cursor()
    
    try:
        # Insert trace
        cursor.execute("""
            INSERT INTO traces (id, name, agent_name, status, start_time, end_time, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace.id,
            trace.name,
            trace.agent_name,
            trace.status,
            trace.start_time,
            trace.end_time,
            trace.duration_ms,
            json.dumps(trace.metadata)
        ))
        
        # Insert spans
        for span in trace.spans:
            cursor.execute("""
                INSERT INTO spans (id, trace_id, parent_id, name, span_type, status, start_time, end_time, duration_ms, metadata, token_usage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                span.id,
                span.trace_id,
                span.parent_id,
                span.name,
                span.span_type,
                span.status,
                span.start_time,
                span.end_time,
                span.duration_ms,
                json.dumps(span.metadata),
                json.dumps(span.token_usage.dict() if span.token_usage else None)
            ))
        
        db.commit()
        
        # Broadcast to WebSocket clients
        await broadcast_trace(trace.dict())
        
        return {"status": "success", "trace_id": trace.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions", response_model=List[TraceResponse])
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db)
):
    """List all traces/sessions."""
    query = "SELECT * FROM traces"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    traces = []
    for row in rows:
        traces.append(row_to_trace(row))
    
    return traces

@app.get("/sessions/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Get a specific trace by ID."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM traces WHERE id = ?", (trace_id,))
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return row_to_trace(row)

@app.get("/sessions/{trace_id}/trace")
async def get_trace_detail(trace_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Get detailed trace information (alias for get_trace)."""
    return await get_trace(trace_id, db)

@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live trace updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive - client can send ping/pong
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def broadcast_trace(trace_data: dict):
    """Broadcast trace data to all connected WebSocket clients."""
    await manager.broadcast({
        "type": "trace_update",
        "payload": trace_data
    })

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "glassbox-backend", "version": "0.1.0"}

# Statistics endpoint
@app.get("/stats")
async def get_stats(db: sqlite3.Connection = Depends(get_db)):
    """Get basic statistics about stored traces."""
    cursor = db.cursor()
    
    # Total traces
    cursor.execute("SELECT COUNT(*) FROM traces")
    total_traces = cursor.fetchone()[0]
    
    # Total spans
    cursor.execute("SELECT COUNT(*) FROM spans")
    total_spans = cursor.fetchone()[0]
    
    # Status breakdown
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM traces 
        GROUP BY status
    """)
    status_counts = dict(cursor.fetchall())
    
    # Recent activity (last hour)
    cursor.execute("""
        SELECT COUNT(*) FROM traces 
        WHERE datetime(start_time) > datetime('now', '-1 hour')
    """)
    recent_traces = cursor.fetchone()[0]
    
    return {
        "total_traces": total_traces,
        "total_spans": total_spans,
        "status_counts": status_counts,
        "recent_traces_last_hour": recent_traces
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
