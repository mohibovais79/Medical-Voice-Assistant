"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    All values are read from environment variables (see `.env.example`).
    Never commit real secrets — keep them in `.env` (gitignored).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    port: int = 8000
    environment: Literal["development", "production"] = "development"

    # --- Database (Supabase Postgres via direct connection) ---
    # Accepts either DATABASE_URL or SUPABASE_CONN in .env
    database_url: str = ""
    supabase_conn: Optional[str] = None  # legacy alias, merged into database_url below

    # --- Groq ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Vapi ---
    vapi_api_key: str = ""
    vapi_public_key: str = ""
    vapi_assistant_id: str = ""
    vapi_server_url: str = ""

    def model_post_init(self, __context) -> None:
        """If database_url is empty but supabase_conn is set, use it."""
        if not self.database_url and self.supabase_conn:
            self.database_url = self.supabase_conn

    @property
    def is_configured(self) -> bool:
        """True if the minimum required secrets are present."""
        return bool(self.database_url and self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — single source of truth for config."""
    return Settings()
