"""Deterministic sampling and blank, reviewer-facing human audit templates."""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Iterable

from composio_research.config import AUDIT_DIR, PASS1_DIR, PASS2_DIR
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
    agent_evidence_urls: tuple[str, ...]
    evidence_missing: bool
    sample_type: AuditSampleType
    reviewer_instructions: str
    human_ground_truth: str | None = None
    correct: bool | None = None
    note: str = ""


def _rank(record: AppRecord, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{record.id}".encode()).hexdigest()


def representative_sample(records: Iterable[AppRecord], *, size: int = 12) -> tuple[AppRecord, ...]:
    """Choose a deterministic sample covering categories and major verdict types."""
    pool = tuple(records)
    chosen: list[AppRecord] = []
    # First cover every available verdict, then greedily maximize coverage of
    # unseen categories and category×verdict cells with deterministic ties.
    for verdict in sorted({record.buildability_verdict.value for record in pool}):
        candidates = [record for record in pool if record.buildability_verdict.value == verdict]
        chosen.append(min(candidates, key=lambda record: _rank(record, "representative-verdict")))
    while len(chosen) < min(size, len(pool)):
        remaining = [record for record in pool if record not in chosen]
        categories = {record.category for record in chosen}
        cells = {(record.category, record.buildability_verdict.value) for record in chosen}
        chosen.append(max(remaining, key=lambda record: (
            int(record.category not in categories),
            int((record.category, record.buildability_verdict.value) not in cells),
            _rank(record, "representative-fill"),
        )))
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
    """Use the same readable enum representation shown to a human reviewer.

    Lists remain JSON so an ordered multi-auth prediction is unambiguous. A
    scalar enum must not be JSON encoded: that adds quotation marks and makes
    an otherwise identical human-audit value fail validation.
    """
    value = getattr(record, field)
    if isinstance(value, list):
        return json.dumps(value, default=lambda item: item.value, ensure_ascii=False)
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _official_evidence_urls(record: AppRecord, field: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        evidence.url for evidence in record.evidence
        if evidence.field == field and evidence.source_type != EvidenceSourceType.SECONDARY
    ))


def build_audit_templates(
    records: Iterable[AppRecord],
    *,
    pass2_records: Iterable[AppRecord] = (),
    representative_size: int = 12,
    challenge_size: int = 5,
) -> tuple[AuditTemplate, ...]:
    """Build reviewer tasks without writing a human verdict or changing a record."""
    records = tuple(records)
    representative = representative_sample(records, size=representative_size)
    challenge = challenge_sample(records, size=challenge_size, exclude_ids={record.id for record in representative})
    templates: list[AuditTemplate] = []
    pass2_by_id = {record.id: record for record in pass2_records}
    for sample_type, selected in ((AuditSampleType.REPRESENTATIVE, representative), (AuditSampleType.CHALLENGE, challenge)):
        for original in selected:
            # Audit the same fields on pass two when it exists, enabling a
            # valid paired pass-one/pass-two accuracy comparison.
            records_for_sample = (original,) + ((pass2_by_id[original.id],) if original.id in pass2_by_id else ())
            for record in records_for_sample:
                for field in AUDITED_FIELDS:
                    urls = _official_evidence_urls(record, field)
                    templates.append(AuditTemplate(
                        app_id=record.id,
                        app=record.app,
                        category=record.category,
                        pass_number=record.pass_number,
                        field=field,
                        frozen_agent_value=_field_value(record, field),
                        agent_evidence_urls=urls,
                        evidence_missing=not urls,
                        sample_type=sample_type,
                        reviewer_instructions="Check the agent evidence links where present, independently find official evidence if needed, enter ground truth, mark correctness, and explain any disagreement.",
                    ))
    return tuple(templates)


def load_records(directory: Path = PASS1_DIR) -> tuple[AppRecord, ...]:
    return tuple(AppRecord.model_validate(read_json(path)) for path in sorted(directory.glob("*.json")))


def load_pass2_records(directory: Path = PASS2_DIR) -> tuple[AppRecord, ...]:
    return load_records(directory)


def save_audit_templates(templates: tuple[AuditTemplate, ...], path: Path = AUDIT_DIR / "audit_template.json") -> Path:
    write_json(path, templates)
    return path
