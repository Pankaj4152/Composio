"""Tests that narratives remain mechanically tied to computed data."""

from composio_research.insights import generate_insights
from composio_research.schema import BlockerType, CredentialAccess
from test_research import make_record


def test_insights_include_computed_counts_and_unknown_coverage_caveat() -> None:
    records = (
        make_record(id=1, app="One", credential_access=CredentialAccess.FREE_SELF_SERVE, blocker_type=BlockerType.NONE),
        make_record(id=2, app="Two", credential_access=CredentialAccess.CONTACT_SALES, blocker_type=BlockerType.CONTACT_SALES),
    )
    report = generate_insights(records)
    by_key = {finding.key: finding for finding in report.findings}

    assert report.record_count == 2
    assert "2" in by_key["composio_coverage_caveat"].detail
    assert by_key["easy_build_opportunity"].supporting_app_ids == (1,)
    assert by_key["leading_blocker"].supporting_app_ids == (2,)
