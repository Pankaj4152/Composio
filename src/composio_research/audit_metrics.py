"""Score completed human audit records while keeping frozen predictions intact."""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from composio_research.config import AUDIT_DIR
from composio_research.schema import AuditSampleType, HumanAuditRecord
from composio_research.serialization import read_json, write_json


@dataclass(frozen=True, slots=True)
class AccuracyMetric:
    sample_type: AuditSampleType
    field: str
    pass_number: int
    checked: int
    correct: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class AuditScorecard:
    metrics: tuple[AccuracyMetric, ...]
    paired_pass_comparison: tuple[AccuracyMetric, ...]


def load_completed_audits(path: Path) -> tuple[HumanAuditRecord, ...]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError("Completed audit file must be a JSON array.")
    return tuple(HumanAuditRecord.model_validate(item) for item in data)


def _metrics(records: tuple[HumanAuditRecord, ...]) -> tuple[AccuracyMetric, ...]:
    groups: dict[tuple[AuditSampleType, str, int], list[HumanAuditRecord]] = defaultdict(list)
    for record in records:
        groups[(record.sample_type, record.field, record.pass_number)].append(record)
    return tuple(
        AccuracyMetric(sample_type, field, pass_number, len(group), sum(item.correct for item in group), sum(item.correct for item in group) / len(group))
        for (sample_type, field, pass_number), group in sorted(groups.items(), key=lambda item: (item[0][0].value, item[0][1], item[0][2]))
    )


def score_audits(records: tuple[HumanAuditRecord, ...]) -> AuditScorecard:
    """Score all completed records and the paired subset valid for pass comparison."""
    by_key: dict[tuple[int, str, AuditSampleType], set[int]] = defaultdict(set)
    for record in records:
        by_key[(record.app_id, record.field, record.sample_type)].add(record.pass_number)
    paired_keys = {key for key, passes in by_key.items() if {1, 2}.issubset(passes)}
    paired = tuple(record for record in records if (record.app_id, record.field, record.sample_type) in paired_keys)
    return AuditScorecard(metrics=_metrics(records), paired_pass_comparison=_metrics(paired))


def save_scorecard(scorecard: AuditScorecard, path: Path = AUDIT_DIR / "scorecard.json") -> Path:
    write_json(path, scorecard)
    return path
