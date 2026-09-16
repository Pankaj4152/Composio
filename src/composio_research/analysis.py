"""Deterministic product-ops analysis derived exclusively from frozen records."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from composio_research.config import PASS1_DIR, PASS2_DIR, REPORT_DIR
from composio_research.schema import ApiBreadth, ApiSurface, AppRecord, BlockerType, CredentialAccess, MCPStatus
from composio_research.serialization import read_json, write_json


SELF_SERVE_ACCESS = frozenset({CredentialAccess.FREE_SELF_SERVE, CredentialAccess.TRIAL_SELF_SERVE, CredentialAccess.PAID_SELF_SERVE})
GATED_ACCESS = frozenset({CredentialAccess.ADMIN_APPROVAL, CredentialAccess.APP_REVIEW, CredentialAccess.ENTERPRISE_PLAN, CredentialAccess.PARTNER_ONLY, CredentialAccess.CONTACT_SALES})
USEFUL_API = frozenset({ApiSurface.REST, ApiSurface.GRAPHQL, ApiSurface.REST_AND_GRAPHQL, ApiSurface.RPC_OR_OTHER})
MEANINGFUL_BREADTH = frozenset({ApiBreadth.MODERATE, ApiBreadth.BROAD})


@dataclass(frozen=True, slots=True)
class OpportunitySets:
    easy_build: tuple[int, ...]
    strategic_outreach: tuple[int, ...]
    investigate_or_deprioritize: tuple[int, ...]
    api_accessible_no_mcp: tuple[int, ...]
    composio_gap: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    record_count: int
    selected_pass_by_app: dict[int, int]
    auth_distribution: dict[str, int]
    access_distribution: dict[str, int]
    buildability_distribution: dict[str, int]
    blocker_distribution: dict[str, int]
    mcp_distribution: dict[str, int]
    confidence_distribution: dict[str, int]
    composio_coverage: dict[str, int]
    category_verdict_matrix: dict[str, dict[str, int]]
    category_access_matrix: dict[str, dict[str, int]]
    opportunities: OpportunitySets


def _counter(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def select_final_records(pass1_records: Iterable[AppRecord], pass2_records: Iterable[AppRecord]) -> tuple[AppRecord, ...]:
    """Prefer frozen pass two where available, otherwise retain frozen pass one."""
    selected = {record.id: record for record in pass1_records}
    selected.update({record.id: record for record in pass2_records})
    return tuple(selected[app_id] for app_id in sorted(selected))


def _matrix(records: Iterable[AppRecord], attribute: str) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        value = getattr(record, attribute)
        matrix[record.category][value.value] += 1
    return {category: dict(sorted(counts.items())) for category, counts in sorted(matrix.items())}


def _confidence_band(value: float) -> str:
    if value >= 0.9:
        return "high"
    if value >= 0.75:
        return "medium"
    return "low"


def analyze(records: Iterable[AppRecord]) -> AnalysisResult:
    """Compute all distributions and transparent opportunity segments from records."""
    records = tuple(records)
    easy = []
    outreach = []
    investigate = []
    accessible_no_mcp = []
    composio_gap = []
    for record in records:
        api_useful = record.api_surface in USEFUL_API and record.api_breadth in MEANINGFUL_BREADTH
        self_serve = record.credential_access in SELF_SERVE_ACCESS
        gated = record.credential_access in GATED_ACCESS
        no_hard_blocker = record.blocker_type == BlockerType.NONE
        no_mcp = record.mcp_status in {MCPStatus.NONE_FOUND, MCPStatus.UNKNOWN}
        if api_useful and self_serve and no_hard_blocker:
            easy.append(record.id)
        elif api_useful and gated:
            outreach.append(record.id)
        else:
            investigate.append(record.id)
        if api_useful and self_serve and no_mcp:
            accessible_no_mcp.append(record.id)
        if record.composio_has_toolkit is False:
            composio_gap.append(record.id)

    return AnalysisResult(
        record_count=len(records),
        selected_pass_by_app={record.id: record.pass_number for record in records},
        auth_distribution=_counter(method.value for record in records for method in record.auth_methods),
        access_distribution=_counter(record.credential_access.value for record in records),
        buildability_distribution=_counter(record.buildability_verdict.value for record in records),
        blocker_distribution=_counter(record.blocker_type.value for record in records),
        mcp_distribution=_counter(record.mcp_status.value for record in records),
        confidence_distribution=_counter(_confidence_band(record.overall_confidence) for record in records),
        composio_coverage=_counter("covered" if record.composio_has_toolkit is True else "gap" if record.composio_has_toolkit is False else "unknown" for record in records),
        category_verdict_matrix=_matrix(records, "buildability_verdict"),
        category_access_matrix=_matrix(records, "credential_access"),
        opportunities=OpportunitySets(tuple(easy), tuple(outreach), tuple(investigate), tuple(accessible_no_mcp), tuple(composio_gap)),
    )


def load_final_records(pass1_dir: Path = PASS1_DIR, pass2_dir: Path = PASS2_DIR) -> tuple[AppRecord, ...]:
    pass1 = tuple(AppRecord.model_validate(read_json(path)) for path in sorted(pass1_dir.glob("*.json")))
    pass2 = tuple(AppRecord.model_validate(read_json(path)) for path in sorted(pass2_dir.glob("*.json")))
    return select_final_records(pass1, pass2)


def save_analysis(result: AnalysisResult, path: Path = REPORT_DIR / "analysis.json") -> Path:
    write_json(path, result)
    return path
