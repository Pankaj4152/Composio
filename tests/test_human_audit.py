"""Tests for deterministic and non-fabricated audit task generation."""

from composio_research.human_audit import build_audit_templates, challenge_sample, representative_sample
from test_research import make_record


def records():
    categories = ["A", "B", "C"]
    return tuple(
        make_record(id=index, app=f"App {index}", category=categories[(index - 1) % len(categories)], overall_confidence=0.1 * index)
        for index in range(1, 7)
    )


def test_representative_sample_is_stratified_and_deterministic() -> None:
    first = representative_sample(records(), size=3)
    second = representative_sample(records(), size=3)

    assert first == second
    assert {record.category for record in first} == {"A", "B", "C"}


def test_challenge_sample_prioritizes_low_confidence() -> None:
    selected = challenge_sample(records(), size=2)

    assert [record.id for record in selected] == [1, 2]


def test_audit_templates_are_blank_and_include_frozen_values() -> None:
    templates = build_audit_templates(records(), representative_size=2, challenge_size=1)

    assert all(template.human_ground_truth is None and template.correct is None for template in templates)
    assert {template.field for template in templates} == {"auth_methods", "credential_access", "api_surface", "mcp_status", "buildability_verdict"}
