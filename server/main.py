"""
GLASS BOX Backend Main Entry Point
"""

import uvicorn
from server.server.app import app

if __name__ == "__main__":
    uvicorn.run(
        "server.server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )