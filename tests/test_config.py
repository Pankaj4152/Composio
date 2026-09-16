"""Tests for environment-backed runtime settings."""

import pytest
from pydantic import ValidationError

from composio_research.config import Settings


def test_settings_use_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.max_concurrency == 5
    assert settings.request_timeout_seconds == 30
    assert settings.openai_timeout_seconds == 75
    assert settings.openai_api_key is None


def test_settings_normalize_empty_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("SEARCH_PROVIDER", " tavily ")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key is None
    assert settings.search_provider == "tavily"


def test_settings_reject_unsafe_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENCY", "0")

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(_env_file=None)
