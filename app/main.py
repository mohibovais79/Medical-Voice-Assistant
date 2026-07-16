"""FastAPI application factory + ASGI entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

Run in production (Render):
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import patients_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.voice import voice_router

setup_logging()
log = get_logger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Medical Voice Assistant — Patient Registration API",
        description=(
            "Voice AI agent + REST API for U.S. patient demographic intake. "
            "Callers register via a phone call powered by Vapi + Groq; records "
            "are persisted to Supabase Postgres and exposed via this API."
        ),
        version="0.1.0",
    )

    # CORS — allow the (optional) dashboard and Vapi's servers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(patients_router)
    app.include_router(voice_router)

    @app.get("/health", tags=["meta"])
    def health():
        return {
            "status": "ok",
            "configured": settings.is_configured,
            "environment": settings.environment,
        }

    # Serve the dashboard (static HTML+JS in dist/)
    # API routes take priority; frontend is fallback for non-API paths.
    app.frontend("/", directory="dist", fallback="index.html")

    log.info("App initialized (env=%s, configured=%s)", settings.environment, settings.is_configured)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
    )
