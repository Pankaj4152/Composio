"""Mocked tests for Tavily/Serper adapters and retrieval integration."""

import httpx
import pytest

from composio_research.apps import APPS
from composio_research.config import Settings
from composio_research.retrieval import discover_candidates
from composio_research.search import (
    SearchConfigurationError,
    SerperSearchProvider,
    TavilySearchProvider,
    create_search_provider,
)
from composio_research.source_planner import CandidateSourceType, plan_research


def test_tavily_adapter_sends_expected_payload_and_parses_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.tavily.com/search"
        assert request.json() if False else True  # Request body is asserted below.
        assert b'"query":"Slack API"' in request.content
        assert b'"max_results":2' in request.content
        return httpx.Response(
            200,
            json={"results": [{"title": "Slack API", "url": "https://api.slack.com", "content": "OAuth"}]},
            request=request,
        )

    provider = TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = provider.search("Slack API", limit=2)

    assert results[0].url == "https://api.slack.com"
    assert results[0].snippet == "OAuth"


def test_serper_adapter_sends_auth_header_and_parses_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://google.serper.dev/search"
        assert request.headers["X-API-KEY"] == "test-key"
        assert b'"q":"Shopify API"' in request.content
        return httpx.Response(
            200,
            json={"organic": [{"title": "Shopify Docs", "link": "https://shopify.dev/docs", "snippet": "Build apps"}]},
            request=request,
        )

    provider = SerperSearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = provider.search("Shopify API")

    assert results[0].title == "Shopify Docs"
    assert results[0].url == "https://shopify.dev/docs"


def test_factory_rejects_missing_or_unsupported_provider() -> None:
    with pytest.raises(SearchConfigurationError, match="SEARCH_PROVIDER"):
        create_search_provider(Settings(_env_file=None))

    with pytest.raises(SearchConfigurationError, match="Unsupported"):
        create_search_provider(
            Settings(search_provider="other", search_api_key="test-key", _env_file=None)
        )


def test_factory_selects_configured_provider() -> None:
    settings = Settings(search_provider="serper", search_api_key="test-key", _env_file=None)
    provider = create_search_provider(settings)
    try:
        assert isinstance(provider, SerperSearchProvider)
    finally:
        provider.close()


def test_search_results_feed_into_official_first_candidate_ranking() -> None:
    class Provider:
        def search(self, query: str, limit: int = 5):
            return [
                type("Result", (), {"title": "Blog", "url": "https://example.test/slack", "snippet": ""})(),
                type("Result", (), {"title": "API docs", "url": "https://api.slack.com/authentication", "snippet": ""})(),
            ]

    slack = next(app for app in APPS if app.name == "Slack")
    candidates = discover_candidates(plan_research(slack), Provider())

    assert candidates[0].source_type == CandidateSourceType.OFFICIAL_HINT
    assert candidates[1].source_type == CandidateSourceType.OFFICIAL_DOCS
