"""
FastAPI main application entry point.
Tigger - A股与数字货币交易分析系统
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services import database as db
from api.routes import trades, screener, crypto, backtest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup: Initialize database
    db.init_db()
    logging.info("Database initialized")
    yield
    # Shutdown: Cleanup (services manage their own threads)


app = FastAPI(
    title="Tigger API",
    description="A-Share & Crypto Trading Analysis System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (Vue SPA) - relative to project root
# Only mount if running outside Docker (when nginx serves static files instead)
import os
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    # Root path - serve index.html
    @app.get("/")
    async def root():
        """Serve the main index.html from static folder."""
        from fastapi.responses import FileResponse
        static_index = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
        return FileResponse(static_index)


# Register route modules
app.include_router(trades.router, prefix="/api", tags=["trades"])
app.include_router(screener.router, prefix="/api", tags=["screener"])
app.include_router(crypto.router, prefix="/api", tags=["crypto"])
app.include_router(backtest.router, prefix="/api", tags=["backtest"])


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Tigger - A 股 & 数字货币交易分析系统")
    print("  FastAPI 迁移版本")
    print("  访问地址: http://127.0.0.1:8002")
    print("  API 文档: http://127.0.0.1:8002/docs")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8002)
