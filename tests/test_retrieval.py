"""Mocked tests for retrieval reliability and source artifact traceability."""

from pathlib import Path

import httpx

from composio_research.apps import APPS
from composio_research.retrieval import (
    Fetcher,
    SearchResult,
    classify_search_result,
    discover_candidates,
    retrieve_plan,
    save_retrieval_artifact,
)
from composio_research.serialization import read_json
from composio_research.source_planner import (
    CandidateSourceType,
    RetrievalStatus,
    plan_research,
)


HTML_PAGE = """
<html>
  <head><title>Developer authentication</title></head>
  <body>
    <nav>Sign in | Pricing | Careers</nav>
    <main><h1>OAuth documentation</h1><p>Use OAuth 2.0 to obtain access tokens.</p></main>
    <footer>Cookie preferences</footer>
  </body>
</html>
"""


def app_by_name(name: str):
    return next(app for app in APPS if app.name == name)


class FakeSearchProvider:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult("Official API", "https://api.slack.com/authentication/oauth-v2"),
            SearchResult("Blog post", "https://example.test/slack-oauth"),
        ][:limit]


def test_classify_search_result_prioritizes_official_docs() -> None:
    official = classify_search_result(
        SearchResult("Slack API", "https://api.slack.com/methods"), "slack.com", "Slack"
    )
    secondary = classify_search_result(
        SearchResult("Blog", "https://example.test/slack"), "slack.com", "Slack"
    )

    assert official.source_type == CandidateSourceType.OFFICIAL_DOCS
    assert official.priority > secondary.priority
    assert secondary.source_type == CandidateSourceType.SECONDARY


def test_official_result_for_the_wrong_google_product_is_downranked_and_flagged() -> None:
    analytics_mcp = classify_search_result(
        SearchResult(
            "Google Analytics MCP server",
            "https://developers.google.com/analytics/devguides/MCP",
            "A search snippet that mentions Google Ads despite the page being about Analytics.",
        ),
        "developers.google.com",
        "Google Ads",
    )
    ads_mcp = classify_search_result(
        SearchResult(
            "Google Ads API MCP server",
            "https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server",
            "Google Ads MCP server documentation.",
        ),
        "developers.google.com",
        "Google Ads",
    )

    assert analytics_mcp.is_official_domain is True
    assert analytics_mcp.relevance_score == 0.6
    assert analytics_mcp.requires_human_review is True
    assert ads_mcp.relevance_score == 1.0
    assert ads_mcp.priority > analytics_mcp.priority


def test_discovery_keeps_direct_hint_and_deduplicates_search_results() -> None:
    plan = plan_research(app_by_name("Slack"))
    candidates = discover_candidates(plan, FakeSearchProvider(), per_query_limit=2)

    assert candidates[0].url == "https://slack.com"
    assert len(candidates) == 3
    assert sum(candidate.url == "https://api.slack.com/authentication/oauth-v2" for candidate in candidates) == 1


def test_fetcher_extracts_clean_main_text_and_keeps_final_url() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=HTML_PAGE, request=request))
    client = httpx.Client(transport=transport, follow_redirects=True)
    plan = plan_research(app_by_name("Slack"))

    source = Fetcher(client=client).fetch(plan.direct_candidates[0])

    assert source.status == RetrievalStatus.FETCHED
    assert source.final_url == "https://slack.com"
    assert source.title == "Developer authentication"
    assert "OAuth 2.0" in (source.extracted_text or "")
    assert "Cookie preferences" not in (source.extracted_text or "")


def test_fetcher_retries_transient_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="Temporary failure", request=request)
        return httpx.Response(200, text=HTML_PAGE, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    plan = plan_research(app_by_name("Slack"))

    source = Fetcher(client=client, max_attempts=2, backoff_seconds=0).fetch(plan.direct_candidates[0])

    assert source.status == RetrievalStatus.FETCHED
    assert source.attempts == 2
    assert attempts == 2


def test_failed_source_is_recorded_without_crashing_run() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404, request=request))
    client = httpx.Client(transport=transport, follow_redirects=True)
    plan = plan_research(app_by_name("Slack"))

    source = Fetcher(client=client, max_attempts=1).fetch(plan.direct_candidates[0])

    assert source.status == RetrievalStatus.FAILED
    assert source.status_code == 404
    assert source.error


def test_retrieval_artifact_is_saved_with_plan_and_clean_source_text(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=HTML_PAGE, request=request))
    client = httpx.Client(transport=transport, follow_redirects=True)
    plan = plan_research(app_by_name("Slack"))
    artifact = retrieve_plan(plan, Fetcher(client=client))

    path = save_retrieval_artifact(artifact, tmp_path)
    saved = read_json(path)

    assert path == tmp_path / "retrieval" / "021.json"
    assert saved["app_name"] == "Slack"
    assert saved["fetched_sources"][0]["status"] == "fetched"
    assert saved["fetched_sources"][0]["relevance_score"] == 1.0
    assert saved["fetched_sources"][0]["requires_human_review"] is False
    assert "OAuth 2.0" in saved["fetched_sources"][0]["extracted_text"]


def test_retrieval_limits_the_number_of_fetched_candidates() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, text=HTML_PAGE, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    plan = plan_research(app_by_name("Slack"))
    artifact = retrieve_plan(
        plan,
        Fetcher(client=client),
        FakeSearchProvider(),
        per_query_limit=2,
        max_candidates=2,
    )

    assert len(artifact.fetched_sources) == 2
    assert requests == 2


def test_retrieval_deduplicates_a_redirected_hint_and_matching_search_result() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == "https://shopify.dev":
            return httpx.Response(
                302,
                headers={"Location": "https://shopify.dev/docs"},
                request=request,
            )
        return httpx.Response(200, text=HTML_PAGE, request=request)

    class ShopifyProvider:
        def search(self, query: str, limit: int = 5):
            return [SearchResult("Shopify Dev Docs", "https://shopify.dev/docs")]

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    shopify = app_by_name("Shopify")
    artifact = retrieve_plan(
        plan_research(shopify),
        Fetcher(client=client),
        ShopifyProvider(),
        max_candidates=3,
    )

    assert len(artifact.fetched_sources) == 1
    assert artifact.fetched_sources[0].final_url == "https://shopify.dev/docs"
    assert requests.count("https://shopify.dev/docs") == 1
