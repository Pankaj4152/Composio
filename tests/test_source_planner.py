"""Tests for official-first source planning without network access."""

from composio_research.apps import APPS
from composio_research.source_planner import (
    CandidateSourceType,
    RetrievalStatus,
    is_official_url,
    parse_hint,
    plan_research,
)


def app_by_name(name: str):
    return next(app for app in APPS if app.name == name)


def test_parse_hint_normalizes_domain_and_docs_path() -> None:
    slack_hint = parse_hint("slack.com")
    google_ads_hint = parse_hint("developers.google.com/google-ads")

    assert slack_hint.direct_url == "https://slack.com"
    assert slack_hint.official_domain == "slack.com"
    assert google_ads_hint.direct_url == "https://developers.google.com/google-ads"
    assert google_ads_hint.official_domain == "developers.google.com"


def test_parse_hint_preserves_non_url_hint_without_inventing_a_domain() -> None:
    paygent_hint = parse_hint("paygent (NMI-powered)")

    assert paygent_hint.direct_url is None
    assert paygent_hint.official_domain is None


def test_plan_uses_supplied_official_hint_before_search_results() -> None:
    plan = plan_research(app_by_name("Shopify"))

    assert len(plan.direct_candidates) == 1
    candidate = plan.direct_candidates[0]
    assert candidate.url == "https://shopify.dev"
    assert candidate.source_type == CandidateSourceType.OFFICIAL_HINT
    assert candidate.priority == 100
    assert candidate.status == RetrievalStatus.PLANNED
    assert all(query.query.startswith('site:shopify.dev "Shopify"') for query in plan.queries)


def test_plan_uses_unscoped_queries_when_assignment_hint_is_not_a_url() -> None:
    plan = plan_research(app_by_name("Paygent Connect"))

    assert plan.direct_candidates == ()
    assert all(query.query.startswith('"Paygent Connect"') for query in plan.queries)
    assert all("site:" not in query.query for query in plan.queries)


def test_query_plan_covers_api_auth_access_and_mcp() -> None:
    plan = plan_research(app_by_name("Slack"))
    purposes = [query.purpose for query in plan.queries]

    assert len(plan.queries) == 4
    assert any("API and developer" in purpose for purpose in purposes)
    assert any("authentication" in purpose for purpose in purposes)
    assert any("credential gates" in purpose for purpose in purposes)
    assert any("MCP" in purpose for purpose in purposes)


def test_official_domain_check_rejects_lookalike_domains() -> None:
    assert is_official_url("https://api.slack.com/methods", "slack.com")
    assert not is_official_url("https://slack.com.example.test/docs", "slack.com")
    assert not is_official_url("https://not-slack.com/docs", "slack.com")
