"""Tests for conservative, read-only Composio catalog matching."""

from composio_research.composio_check import ComposioCatalogChecker, normalize_name
from composio_research.config import Settings


class FakeToolkits:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return {"items": self.items}


class FakeComposio:
    def __init__(self, items):
        self.toolkits = FakeToolkits(items)


def test_normalize_name_is_stable() -> None:
    assert normalize_name("Google-Ads!") == "google ads"


def test_catalog_checker_returns_exact_match_only() -> None:
    client = FakeComposio([{"name": "GitHub", "slug": "github"}, {"name": "Slack", "slug": "slack"}])
    result = ComposioCatalogChecker(Settings(_env_file=None), client=client).check("GitHub")

    assert result.has_toolkit is True
    assert result.matched_slug == "github"
    assert client.toolkits.calls == [{"limit": 100, "cursor": None}]


def test_catalog_checker_marks_near_match_unknown() -> None:
    client = FakeComposio([{"name": "Google Ads Manager", "slug": "google_ads_manager"}])
    result = ComposioCatalogChecker(Settings(_env_file=None), client=client).check("Google Ads")

    assert result.has_toolkit is None
    assert "Possible" in result.notes


def test_catalog_checker_is_graceful_without_key() -> None:
    result = ComposioCatalogChecker(Settings(_env_file=None)).check("Slack")

    assert result.has_toolkit is None
    assert "COMPOSIO_API_KEY" in result.notes


def test_catalog_checker_redacts_key_like_provider_error() -> None:
    class BrokenToolkits:
        def list(self, **kwargs):
            raise RuntimeError("Invalid API key: ck_secretValue")
    class BrokenClient:
        toolkits = BrokenToolkits()
    result = ComposioCatalogChecker(Settings(_env_file=None), client=BrokenClient()).check("Slack")
    assert "ck_secretValue" not in result.notes
    assert "[redacted]" in result.notes
