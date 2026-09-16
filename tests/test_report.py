"""Tests for data-honest static case-study rendering."""

from composio_research.report import render_report
from test_research import make_record


def test_report_uses_actual_record_count_and_escapes_findings() -> None:
    html = render_report(
        {"record_count": 3, "buildability_distribution": {"build_now": 3}, "opportunities": {}, "category_verdict_matrix": {}, "category_access_matrix": {}},
        {"findings": [{"headline": "<unsafe>", "detail": "3 of 3", "supporting_app_ids": [1, 2, 3]}]},
    )

    assert "partial analysis of 3 frozen records" in html
    assert "<unsafe>" not in html
    assert "&lt;unsafe&gt;" in html
    assert "100-app result" in html


def test_report_marks_full_dataset_when_count_is_100() -> None:
    html = render_report({"record_count": 100, "buildability_distribution": {}, "opportunities": {}, "category_verdict_matrix": {}, "category_access_matrix": {}}, {"findings": []})

    assert "complete 100-app analysis" in html


def test_report_includes_searchable_evidence_table() -> None:
    html = render_report({"record_count": 1, "buildability_distribution": {}, "opportunities": {}, "category_verdict_matrix": {}, "category_access_matrix": {}}, {"findings": []}, records=(make_record(),))
    assert "app-filter" in html
    assert "Slack" in html
    assert "Evidence-backed app records" in html
