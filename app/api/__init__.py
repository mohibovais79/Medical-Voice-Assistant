"""API package — REST endpoints for patients."""

from app.api.patients import router as patients_router

__all__ = ["patients_router"]
