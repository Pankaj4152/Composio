"""Generate concise, data-backed Product Ops findings without pre-written claims."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from composio_research.analysis import AnalysisResult, analyze, load_final_records
from composio_research.config import REPORT_DIR
from composio_research.schema import AppRecord
from composio_research.serialization import write_json


@dataclass(frozen=True, slots=True)
class Finding:
    key: str
    headline: str
    detail: str
    supporting_app_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class InsightReport:
    record_count: int
    findings: tuple[Finding, ...]


def _top(distribution: dict[str, int], *, exclude: set[str] | None = None) -> tuple[str, int] | None:
    candidates = [(key, count) for key, count in distribution.items() if key not in (exclude or set())]
    return max(candidates, key=lambda item: (item[1], item[0])) if candidates else None


def _ids(records: tuple[AppRecord, ...], predicate) -> tuple[int, ...]:
    return tuple(record.id for record in records if predicate(record))


def generate_insights(records: tuple[AppRecord, ...]) -> InsightReport:
    """Return only observations whose displayed count is directly computed from records."""
    result: AnalysisResult = analyze(records)
    findings: list[Finding] = []
    top_verdict = _top(result.buildability_distribution)
    if top_verdict:
        verdict, count = top_verdict
        findings.append(Finding(
            "dominant_buildability",
            f"{verdict.replace('_', ' ')} is the most common current integration state.",
            f"{count} of {result.record_count} analyzed apps are classified as {verdict}.",
            _ids(records, lambda record: record.buildability_verdict.value == verdict),
        ))
    top_access = _top(result.access_distribution)
    if top_access:
        access, count = top_access
        findings.append(Finding(
            "dominant_access",
            f"{access.replace('_', ' ')} is the most common developer-access condition.",
            f"{count} of {result.record_count} analyzed apps have this access classification.",
            _ids(records, lambda record: record.credential_access.value == access),
        ))
    blocker = _top(result.blocker_distribution, exclude={"none"})
    if blocker:
        blocker_name, count = blocker
        findings.append(Finding(
            "leading_blocker",
            f"{blocker_name.replace('_', ' ')} is the most frequent non-clear blocker.",
            f"It appears on {count} analyzed apps and should guide documentation or partnership follow-up.",
            _ids(records, lambda record: record.blocker_type.value == blocker_name),
        ))
    easy_ids = result.opportunities.easy_build
    findings.append(Finding(
        "easy_build_opportunity",
        "Easy-build opportunity set is defined by useful API, self-serve access, and no hard blocker.",
        f"{len(easy_ids)} of {result.record_count} apps currently meet that transparent rule.",
        easy_ids,
    ))
    outreach_ids = result.opportunities.strategic_outreach
    findings.append(Finding(
        "outreach_opportunity",
        "Strategic outreach candidates have useful APIs but an access gate.",
        f"{len(outreach_ids)} of {result.record_count} apps currently meet that transparent rule.",
        outreach_ids,
    ))
    coverage = result.composio_coverage
    if coverage.get("unknown", 0):
        findings.append(Finding(
            "composio_coverage_caveat",
            "Composio coverage is incomplete or unverified for part of the dataset.",
            f"{coverage['unknown']} of {result.record_count} records have unknown Composio coverage, so they are excluded from gap claims.",
            _ids(records, lambda record: record.composio_has_toolkit is None),
        ))
    return InsightReport(result.record_count, tuple(findings))


def save_insights(report: InsightReport, path: Path = REPORT_DIR / "insights.json") -> Path:
    write_json(path, report)
    return path


def build_insights_from_frozen_records() -> InsightReport:
    return generate_insights(load_final_records())
