"""Deterministic sampling and blank, reviewer-facing human audit templates."""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from composio_research.config import AUDIT_DIR, PASS1_DIR
from composio_research.schema import AppRecord, AuditSampleType, EvidenceSourceType
from composio_research.serialization import read_json, write_json


AUDITED_FIELDS = ("auth_methods", "credential_access", "api_surface", "mcp_status", "buildability_verdict")


@dataclass(frozen=True, slots=True)
class AuditTemplate:
    """A blank review row. This is intentionally not a completed HumanAuditRecord."""

    app_id: int
    app: str
    category: str
    pass_number: int
    field: str
    frozen_agent_value: str
    official_evidence_url: str | None
    sample_type: AuditSampleType
    reviewer_instructions: str
    human_ground_truth: str | None = None
    correct: bool | None = None
    note: str = ""


def _rank(record: AppRecord, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{record.id}".encode()).hexdigest()


def representative_sample(records: Iterable[AppRecord], *, size: int = 12) -> tuple[AppRecord, ...]:
    """Choose category-stratified records deterministically, then fill remaining slots fairly."""
    pool = tuple(records)
    by_category: dict[str, list[AppRecord]] = defaultdict(list)
    for record in pool:
        by_category[record.category].append(record)
    chosen: list[AppRecord] = []
    for category in sorted(by_category):
        chosen.append(min(by_category[category], key=lambda record: _rank(record, "representative-category")))
    remaining = [record for record in pool if record not in chosen]
    chosen.extend(sorted(remaining, key=lambda record: _rank(record, "representative-fill"))[:max(0, size - len(chosen))])
    return tuple(sorted(chosen[:size], key=lambda record: record.id))


def challenge_sample(records: Iterable[AppRecord], *, size: int = 5, exclude_ids: set[int] | None = None) -> tuple[AppRecord, ...]:
    """Prioritize uncertain, gated, or ambiguous records that are likely to reveal failures."""
    excluded = exclude_ids or set()
    pool = [record for record in records if record.id not in excluded]
    def challenge_key(record: AppRecord) -> tuple[float, int, str]:
        uncertainty = int(record.credential_access.value in {"unclear", "partner_only", "contact_sales", "enterprise_plan"})
        ambiguity = int(record.api_surface.value == "unknown" or record.mcp_status.value == "unknown")
        return (record.overall_confidence, -(uncertainty + ambiguity), _rank(record, "challenge"))
    return tuple(sorted(pool, key=challenge_key)[:size])


def _field_value(record: AppRecord, field: str) -> str:
    return json.dumps(getattr(record, field), default=lambda value: value.value, ensure_ascii=False)


def _official_evidence_url(record: AppRecord, field: str) -> str | None:
    matching = [evidence for evidence in record.evidence if evidence.field == field and evidence.source_type != EvidenceSourceType.SECONDARY]
    return matching[0].url if matching else None


def build_audit_templates(records: Iterable[AppRecord], *, representative_size: int = 12, challenge_size: int = 5) -> tuple[AuditTemplate, ...]:
    """Build reviewer tasks without writing a human verdict or changing a record."""
    records = tuple(records)
    representative = representative_sample(records, size=representative_size)
    challenge = challenge_sample(records, size=challenge_size, exclude_ids={record.id for record in representative})
    templates: list[AuditTemplate] = []
    for sample_type, selected in ((AuditSampleType.REPRESENTATIVE, representative), (AuditSampleType.CHALLENGE, challenge)):
        for record in selected:
            for field in AUDITED_FIELDS:
                templates.append(AuditTemplate(
                    app_id=record.id,
                    app=record.app,
                    category=record.category,
                    pass_number=record.pass_number,
                    field=field,
                    frozen_agent_value=_field_value(record, field),
                    official_evidence_url=_official_evidence_url(record, field),
                    sample_type=sample_type,
                    reviewer_instructions="Check the linked official source, enter independent ground truth, mark correct, and explain disagreements.",
                ))
    return tuple(templates)


def load_records(directory: Path = PASS1_DIR) -> tuple[AppRecord, ...]:
    return tuple(AppRecord.model_validate(read_json(path)) for path in sorted(directory.glob("*.json")))


def save_audit_templates(templates: tuple[AuditTemplate, ...], path: Path = AUDIT_DIR / "audit_template.json") -> Path:
    write_json(path, templates)
    return path
