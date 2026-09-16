"""Centralized runtime settings and project paths."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PASS1_DIR = DATA_DIR / "pass1"
PASS2_DIR = DATA_DIR / "pass2"
LOG_DIR = DATA_DIR / "logs"
AUDIT_DIR = DATA_DIR / "audit"
REPORT_DIR = PROJECT_ROOT / "report"
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and an optional .env file.

    Credential fields remain optional because Phase 1 has no external calls. Later
    commands validate only the credentials they actually require.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_concurrency: int = Field(default=5, ge=1, le=20)
    request_timeout_seconds: int = Field(default=30, ge=1, le=120)

    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    search_provider: str | None = None
    search_api_key: str | None = None
    composio_api_key: str | None = None

    @field_validator(
        "openai_api_key",
        "search_provider",
        "search_api_key",
        "composio_api_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object:
        """Treat empty environment variables as absent rather than usable credentials."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


def load_settings() -> Settings:
    """Construct settings on demand, making environment changes testable."""
    return Settings()
