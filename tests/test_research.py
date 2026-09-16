"""Tests for structured extraction and deterministic evidence consistency checks."""

import json

import pytest

from composio_research.apps import APPS
from composio_research.config import Settings
from composio_research.research import (
    ResearchExtractionError,
    ResearchExtractor,
    build_research_context,
    validate_record_consistency,
)
from composio_research.retrieval import FetchedSource, RetrievalArtifact, retrieval_artifact_from_dict
from composio_research.serialization import read_json, write_json
from composio_research.schema import (
    ApiBreadth,
    ApiSurface,
    AppRecord,
    AuthMethod,
    BlockerType,
    BuildabilityVerdict,
    CredentialAccess,
    Evidence,
    EvidenceSourceType,
    EvidenceSupport,
    MCPStatus,
)
from composio_research.source_planner import CandidateSourceType, RetrievalStatus, plan_research


def slack_entry():
    return next(app for app in APPS if app.name == "Slack")


def make_retrieval_artifact() -> RetrievalArtifact:
    entry = slack_entry()
    return RetrievalArtifact(
        app_id=entry.id,
        app_name=entry.name,
        plan=plan_research(entry),
        fetched_sources=(
            FetchedSource(
                requested_url="https://docs.slack.dev/authentication/",
                final_url="https://docs.slack.dev/authentication/",
                source_type=CandidateSourceType.OFFICIAL_DOCS,
                is_official_domain=True,
                priority=90,
                relevance_score=1.0,
                requires_human_review=False,
                status=RetrievalStatus.FETCHED,
                status_code=200,
                title="Slack authentication",
                extracted_text="Slack apps use OAuth 2.0.",
                fetched_at="2026-01-01T00:00:00+00:00",
                attempts=1,
            ),
        ),
        created_at="2026-01-01T00:00:00+00:00",
    )


def make_record(**overrides: object) -> AppRecord:
    values: dict[str, object] = {
        "id": 21,
        "app": "Slack",
        "category": "Communications and Messaging",
        "hint": "slack.com",
        "one_liner": "Business messaging platform.",
        "auth_methods": [AuthMethod.OAUTH2],
        "credential_access": CredentialAccess.FREE_SELF_SERVE,
        "api_surface": ApiSurface.REST,
        "api_breadth": ApiBreadth.BROAD,
        "mcp_status": MCPStatus.NONE_FOUND,
        "buildability_verdict": BuildabilityVerdict.BUILD_NOW,
        "blocker_type": BlockerType.NONE,
        "evidence": [
            Evidence(
                field="auth_methods",
                claim="Slack uses OAuth 2.0.",
                url="https://docs.slack.dev/authentication/",
                source_type=EvidenceSourceType.OFFICIAL_DOCS,
                support=EvidenceSupport.DIRECT,
                confidence=0.98,
            )
        ],
        "overall_confidence": 0.98,
        "pass_number": 1,
    }
    values.update(overrides)
    return AppRecord.model_validate(values)


class FakeResponse:
    id = "resp_test"

    def __init__(self, payload: dict[str, object]) -> None:
        self.output_text = json.dumps(payload)


class FakeClient:
    class responses:
        last_kwargs: dict[str, object] | None = None
        response: FakeResponse | None = None

        @classmethod
        def create(cls, **kwargs: object) -> FakeResponse:
            cls.last_kwargs = kwargs
            assert cls.response is not None
            return cls.response


def test_context_contains_clean_source_metadata_not_raw_html() -> None:
    context = build_research_context(slack_entry(), make_retrieval_artifact())

    assert "URL: https://docs.slack.dev/authentication/" in context
    assert "CLEAN_TEXT:" in context
    assert "Slack apps use OAuth 2.0." in context
    assert "<html" not in context


def test_extractor_uses_strict_json_schema_and_overwrites_model_identity() -> None:
    payload = make_record().model_dump(mode="json")
    payload.update({"id": 999, "app": "Wrong", "category": "Wrong", "hint": "wrong"})
    FakeClient.responses.response = FakeResponse(payload)
    extractor = ResearchExtractor(Settings(openai_model="test-model", _env_file=None), client=FakeClient())

    record, artifact = extractor.extract(slack_entry(), make_retrieval_artifact())

    assert record.id == 21
    assert record.app == "Slack"
    assert artifact.response_id == "resp_test"
    assert FakeClient.responses.last_kwargs is not None
    assert FakeClient.responses.last_kwargs["store"] is False
    assert FakeClient.responses.last_kwargs["text"]["format"]["type"] == "json_schema"  # type: ignore[index]
    assert FakeClient.responses.last_kwargs["text"]["format"]["strict"] is True  # type: ignore[index]


def test_consistency_checks_reject_build_now_without_public_api() -> None:
    record = make_record(api_surface=ApiSurface.NONE_PUBLIC)
    issues = validate_record_consistency(record, make_retrieval_artifact())

    assert any(issue.field == "buildability_verdict" for issue in issues)


def test_consistency_checks_reject_evidence_url_absent_from_context() -> None:
    record = make_record(
        evidence=[
            Evidence(
                field="auth_methods",
                claim="Unsupported URL.",
                url="https://invented.example/docs",
                source_type=EvidenceSourceType.OFFICIAL_DOCS,
                support=EvidenceSupport.DIRECT,
                confidence=0.9,
            )
        ]
    )
    issues = validate_record_consistency(record, make_retrieval_artifact())

    assert any(issue.field == "evidence.url" for issue in issues)


def test_extractor_rejects_invalid_model_json() -> None:
    FakeClient.responses.response = FakeResponse({})
    FakeClient.responses.response.output_text = "not-json"
    extractor = ResearchExtractor(Settings(openai_model="test-model", _env_file=None), client=FakeClient())

    with pytest.raises(ResearchExtractionError, match="not valid JSON"):
        extractor.extract(slack_entry(), make_retrieval_artifact())


def test_retrieval_artifact_round_trip_rehydrates_nested_types(tmp_path) -> None:
    original = make_retrieval_artifact()
    path = tmp_path / "retrieval.json"
    write_json(path, original)

    loaded = retrieval_artifact_from_dict(read_json(path))

    assert loaded.plan.app_name == "Slack"
    assert loaded.fetched_sources[0].source_type == CandidateSourceType.OFFICIAL_DOCS
    assert loaded.fetched_sources[0].status == RetrievalStatus.FETCHED
