"""Tests for normalized research and verification data models."""

import pytest
from pydantic import ValidationError

from composio_research.schema import (
    ApiBreadth,
    ApiSurface,
    AppRecord,
    AuthMethod,
    BlockerType,
    BuildabilityVerdict,
    ClaimVerification,
    ConfidenceLabel,
    CredentialAccess,
    Evidence,
    EvidenceSourceType,
    EvidenceSupport,
    HumanAuditRecord,
    MCPStatus,
    VerificationStatus,
)


def make_record(**overrides: object) -> AppRecord:
    values: dict[str, object] = {
        "id": 21,
        "app": "Slack",
        "category": "Communications and Messaging",
        "hint": "slack.com",
        "one_liner": "A business messaging platform.",
        "auth_methods": [AuthMethod.OAUTH2],
        "credential_access": CredentialAccess.FREE_SELF_SERVE,
        "api_surface": ApiSurface.REST,
        "api_breadth": ApiBreadth.BROAD,
        "mcp_status": MCPStatus.UNKNOWN,
        "buildability_verdict": BuildabilityVerdict.BUILD_NOW,
        "blocker_type": BlockerType.NONE,
        "evidence": [
            Evidence(
                field="auth_methods",
                claim="Slack supports OAuth 2.0.",
                url="https://api.slack.com/authentication/oauth-v2",
                source_type=EvidenceSourceType.OFFICIAL_DOCS,
                support=EvidenceSupport.DIRECT,
                excerpt="Slack uses OAuth 2.0.",
                confidence=0.98,
            )
        ],
        "overall_confidence": 0.98,
        "pass_number": 1,
    }
    values.update(overrides)
    return AppRecord.model_validate(values)


def test_sample_app_record_validates_and_serializes_stably() -> None:
    record = make_record()

    assert record.confidence_label == ConfidenceLabel.HIGH
    assert record.model_dump(mode="json")["auth_methods"] == ["oauth2"]
    assert record.model_dump(mode="json")["credential_access"] == "free_self_serve"
    assert record.model_dump(mode="json")["evidence"][0]["source_type"] == "official_docs"


def test_confidence_label_boundaries_are_predictable() -> None:
    assert make_record(overall_confidence=0.90).confidence_label == ConfidenceLabel.HIGH
    assert make_record(overall_confidence=0.75).confidence_label == ConfidenceLabel.MEDIUM
    assert make_record(overall_confidence=0.74).confidence_label == ConfidenceLabel.LOW


def test_record_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        make_record(overall_confidence=1.01)


def test_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        make_record(unplanned_field="not allowed")


def test_claim_verification_validates() -> None:
    result = ClaimVerification(
        app_id=21,
        field="auth_methods",
        claim="Slack supports OAuth 2.0.",
        source_url="https://api.slack.com/authentication/oauth-v2",
        status=VerificationStatus.SUPPORTED,
        explanation="The official authentication page describes the OAuth flow.",
        verifier_confidence=0.99,
    )

    assert result.status == VerificationStatus.SUPPORTED


def test_human_audit_preserves_frozen_prediction_and_ground_truth() -> None:
    audit = HumanAuditRecord(
        app_id=21,
        app="Slack",
        pass_number=2,
        field="mcp_status",
        frozen_agent_value="official",
        human_ground_truth="community",
        correct=False,
        official_evidence_url="https://api.slack.com/",
        note="No vendor-owned MCP evidence was found.",
        sample_type="challenge",
    )

    assert audit.frozen_agent_value == "official"
    assert audit.human_ground_truth == "community"
    assert audit.correct is False
