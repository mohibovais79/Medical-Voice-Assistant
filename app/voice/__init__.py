"""Voice agent package — Vapi webhook + LLM tools + system prompt."""

from app.voice.webhook import router as voice_router

__all__ = ["voice_router"]
