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


def validate_completed_audits(records: tuple[HumanAuditRecord, ...], frozen_records: tuple[object, ...]) -> None:
    """Reject invented/duplicate audit rows before they influence accuracy metrics."""
    from composio_research.human_audit import AUDITED_FIELDS, _field_value
    frozen = {(record.id, record.pass_number): record for record in frozen_records}
    seen: set[tuple[int, int, str, AuditSampleType]] = set()
    for record in records:
        key = (record.app_id, record.pass_number, record.field, record.sample_type)
        if key in seen:
            raise ValueError(f"Duplicate human audit row: {key}")
        seen.add(key)
        source = frozen.get((record.app_id, record.pass_number))
        if source is None:
            raise ValueError(f"Audit references no frozen record: app={record.app_id}, pass={record.pass_number}")
        if record.field not in AUDITED_FIELDS:
            raise ValueError(f"Audit field is outside the required audit set: {record.field}")
        if record.app != source.app or record.frozen_agent_value != _field_value(source, record.field):
            raise ValueError(f"Audit frozen prediction does not match source record: app={record.app_id}, field={record.field}")
        if not record.official_evidence_url.startswith(("https://", "http://")):
            raise ValueError(f"Human audit evidence URL must be HTTP(S): app={record.app_id}, field={record.field}")


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
