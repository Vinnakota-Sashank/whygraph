"""
WhyGraph — FastAPI Application Entry Point
Track 3: Company Brain | WeMakeDevs × FalkorDB Graph Hacks
"""

import os
import sys

# Set UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import config
from backend.api.routes import router
from backend.graph.connection import get_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: verify graph connectivity on startup."""
    print("=" * 60)
    print("  🚀 Starting WhyGraph — Engineering Decision Memory Agent")
    print(f"  📊 FalkorDB Target: {config.FALKORDB_HOST}:{config.FALKORDB_PORT} (Graph: '{config.FALKORDB_GRAPH_NAME}')")
    print(f"  🧠 LLM Provider: {config.LLM_PROVIDER.upper()}")
    print("=" * 60)
    try:
        g = get_graph()
        # Ping test
        g.query("RETURN 1 AS ping")
        print("  ✅ Successfully connected to FalkorDB!")
    except Exception as e:
        print(f"  ⚠️  FalkorDB connection warning: {e}")
        print("     Ensure FalkorDB is running (e.g., docker run -p 6379:6379 falkordb/falkordb)")
    yield
    print("  🛑 Shutting down WhyGraph backend.")


app = FastAPI(
    title="WhyGraph — Engineering Decision Memory",
    description="Proactive Architectural Constraint Enforcement & Dynamic Expertise Graph Agent for FalkorDB Track 3.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(router)

# Health endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "whygraph",
        "falkordb_graph": config.FALKORDB_GRAPH_NAME,
        "llm_provider": config.LLM_PROVIDER,
    }

# Serve Frontend static assets
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"message": "Frontend index.html not found. Access API docs at /docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=config.APP_HOST, port=config.APP_PORT, reload=True)
