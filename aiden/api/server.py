"""FastAPI application factory for the Aiden web server."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiden import __version__
from aiden.api.routes import router as api_router
from aiden.core.config import settings
from aiden.wecom.routes import router as wecom_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Startup
    print(f"╔══════════════════════════════════════════╗")
    print(f"║   Aiden v{__version__} — AI Personal Assistant   ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"Model: {settings.model}")
    print(f"Data dir: {settings.data_dir}")
    print(f"Listening on http://{settings.host}:{settings.port}")
    if settings.wecom_corp_id:
        print(f"企业微信: 已配置 (Agent ID: {settings.wecom_agent_id})")
    else:
        print(f"企业微信: 未配置")
    yield
    # Shutdown
    print("Server shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Aiden — AI Personal Assistant",
        version=__version__,
        description="A modular AI assistant with plugin architecture, "
        "conversation memory, web search, and code analysis.",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(wecom_router, prefix="/api/v1/wecom")

    # Root redirect
    @app.get("/")
    async def root():
        return {
            "name": "Aiden",
            "version": __version__,
            "docs": "/docs",
            "status": "/api/v1/status",
        }

    return app


app = create_app()
