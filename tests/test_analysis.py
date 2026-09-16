"""Tests that analysis totals and opportunity rules are data-derived and stable."""

from composio_research.analysis import analyze, select_final_records
from composio_research.schema import (
    ApiBreadth, ApiSurface, BlockerType, BuildabilityVerdict, CredentialAccess, MCPStatus,
)
from test_research import make_record


def test_pass_two_replaces_only_the_matching_frozen_pass_one_record() -> None:
    first = make_record(id=1, app="One", pass_number=1)
    second = make_record(id=1, app="One", pass_number=2)
    other = make_record(id=2, app="Two", pass_number=1)

    selected = select_final_records((first, other), (second,))

    assert [(record.id, record.pass_number) for record in selected] == [(1, 2), (2, 1)]


def test_analysis_calculates_visible_opportunity_rules() -> None:
    easy = make_record(id=1, app="Easy", category="A", credential_access=CredentialAccess.FREE_SELF_SERVE, api_surface=ApiSurface.REST, api_breadth=ApiBreadth.BROAD, blocker_type=BlockerType.NONE, mcp_status=MCPStatus.NONE_FOUND)
    outreach = make_record(id=2, app="Outreach", category="A", credential_access=CredentialAccess.PARTNER_ONLY, api_surface=ApiSurface.REST, api_breadth=ApiBreadth.BROAD, buildability_verdict=BuildabilityVerdict.OUTREACH, blocker_type=BlockerType.PARTNER_APPROVAL)
    investigate = make_record(id=3, app="Investigate", category="B", api_surface=ApiSurface.NONE_PUBLIC, api_breadth=ApiBreadth.NARROW, blocker_type=BlockerType.NO_PUBLIC_API, buildability_verdict=BuildabilityVerdict.BLOCKED)

    result = analyze((easy, outreach, investigate))

    assert result.record_count == 3
    assert result.opportunities.easy_build == (1,)
    assert result.opportunities.strategic_outreach == (2,)
    assert result.opportunities.investigate_or_deprioritize == (3,)
    assert result.opportunities.api_accessible_no_mcp == (1,)
    assert result.buildability_distribution == {"blocked": 1, "build_now": 1, "outreach": 1}
