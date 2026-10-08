"""
GLASS BOX Backend - FastAPI server for agent observability.

Provides REST API and WebSocket endpoints for receiving, storing, and serving
trace data from the GLASS BOX SDK.
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import json
import uuid
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

# Import our models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'glassbox'))

from glassbox.types import Trace, Span, TokenUsage

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
    
    conn.commit()
    conn.close()

# Pydantic models for API
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
    token_usage: Optional[Dict[str, Any]] = None

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

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Remove broken connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Database dependency
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
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
                json.dumps(span.token_usage) if span.token_usage else None
            ))
        
        db.commit()
        
        # Broadcast to WebSocket clients
        await broadcast_trace(trace.dict())
        
        return {"status": "success", "trace_id": trace.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions", response_model=List[TraceResponse])
async def list_sessions(db: sqlite3.Connection = Depends(get_db)):
    """List all traces/sessions."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM traces ORDER BY start_time DESC")
    rows = cursor.fetchall()
    
    traces = []
    for row in rows:
        trace_id = row['id']
        # Get spans for this trace
        cursor.execute("SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time", (trace_id,))
        span_rows = cursor.fetchall()
        
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
        
        traces.append(TraceResponse(
            id=row['id'],
            name=row['name'],
            agent_name=row['agent_name'],
            status=row['status'],
            start_time=row['start_time'],
            end_time=row['end_time'],
            duration_ms=row['duration_ms'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            spans=spans
        ))
    
    return traces

@app.get("/sessions/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Get a specific trace by ID."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM traces WHERE id = ?", (trace_id,))
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    # Get spans for this trace
    cursor.execute("SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time", (trace_id,))
    span_rows = cursor.fetchall()
    
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

@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live trace updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def broadcast_trace(trace_data: dict):
    """Broadcast trace data to all connected WebSocket clients."""
    await manager.broadcast({
        "type": "trace",
        "data": trace_data
    })

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "glassbox-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)