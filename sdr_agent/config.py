"""Application settings and a default ICP for the demo.

Settings are loaded from environment variables (and a local .env file) using
pydantic-settings, so secrets never live in the code.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import ICP


class Settings(BaseSettings):
    """Runtime configuration, read from environment / .env (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys (loaded from GEMINI_API_KEY / SERPER_API_KEY)
    gemini_api_key: str = ""
    serper_api_key: str = ""

    # Model + tuning
    gemini_model: str = "gemini-2.0-flash"
    enrichment_concurrency: int = 5   # how many websites to scrape at once
    scoring_concurrency: int = 3      # keep low to respect free-tier LLM rate limits
    request_timeout: float = 15.0     # seconds per HTTP request


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once, reused everywhere)."""
    return Settings()


# A ready-to-run demo ICP so the app works out of the box.
DEFAULT_ICP = ICP(
    industry="dental clinics",
    location="Austin, Texas",
    offer="an AI phone receptionist that answers missed calls and books appointments 24/7",
    ideal_description=(
        "Independently-owned dental clinics that rely on phone bookings and likely "
        "miss calls during busy hours or after closing."
    ),
    signals_to_look_for=[
        "No obvious online booking",
        "Small / independent practice",
        "High call volume / missed-call risk",
    ],
)
