"""Tests for audit accuracy and fair pass-one/pass-two comparisons."""

from composio_research.audit_metrics import score_audits
from composio_research.schema import AuditSampleType, HumanAuditRecord


def audit(app_id: int, field: str, pass_number: int, correct: bool, sample_type=AuditSampleType.REPRESENTATIVE) -> HumanAuditRecord:
    return HumanAuditRecord(
        app_id=app_id, app=f"App {app_id}", pass_number=pass_number, field=field,
        frozen_agent_value="value", human_ground_truth="truth", correct=correct,
        official_evidence_url="https://docs.example", sample_type=sample_type,
    )


def test_scorecard_groups_by_field_sample_and_pass() -> None:
    scorecard = score_audits((audit(1, "auth_methods", 1, True), audit(2, "auth_methods", 1, False)))

    assert scorecard.metrics[0].checked == 2
    assert scorecard.metrics[0].accuracy == 0.5
    assert scorecard.paired_pass_comparison == ()


def test_paired_comparison_excludes_unpaired_apps() -> None:
    scorecard = score_audits((
        audit(1, "auth_methods", 1, False), audit(1, "auth_methods", 2, True),
        audit(2, "auth_methods", 1, True),
    ))

    assert [(metric.pass_number, metric.checked, metric.correct) for metric in scorecard.paired_pass_comparison] == [(1, 1, 0), (2, 1, 1)]
