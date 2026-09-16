"""Independent, source-bounded verification of extracted research claims."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from composio_research.config import LOG_DIR, Settings
from composio_research.research import ResponsesClient, openai_strict_json_schema
from composio_research.retrieval import RetrievalArtifact, canonicalize_url
from composio_research.schema import AppRecord, ClaimVerification, Evidence, VerificationStatus
from composio_research.serialization import write_json


VERIFIER_INSTRUCTIONS = """You are an independent evidence verifier.
Assess whether the supplied cleaned source text supports the supplied claim.
Use only that source text. Do not infer missing facts from product knowledge, a
URL, or the claim itself. Return supported only for direct support; use
partially_supported, unsupported, conflicting, or unverifiable when appropriate.
Give a concise explanation grounded in the supplied text.
"""


@dataclass(frozen=True, slots=True)
class VerificationArtifact:
    """Traceable record of one verifier decision, including raw model output."""

    app_id: int
    field: str
    claim: str
    source_url: str
    model: str | None
    response_id: str | None
    raw_output: str | None
    verification: ClaimVerification


class EvidenceVerificationError(RuntimeError):
    """The verifier response could not be converted into a reliable verdict."""


def _unverifiable(app_id: int, evidence: Evidence, reason: str) -> ClaimVerification:
    return ClaimVerification(
        app_id=app_id,
        field=evidence.field,
        claim=evidence.claim,
        source_url=evidence.url,
        status=VerificationStatus.UNVERIFIABLE,
        explanation=reason,
        verifier_confidence=1.0,
    )


class EvidenceVerifier:
    """Verify claims against exactly their cited, previously fetched source."""

    def __init__(self, settings: Settings, *, client: ResponsesClient | None = None) -> None:
        if settings.openai_api_key is None and client is None:
            raise EvidenceVerificationError("OPENAI_API_KEY is required for evidence verification.")
        self.model = settings.openai_model
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=0)
        self.client = client

    def verify(self, record: AppRecord, retrieval_artifact: RetrievalArtifact) -> tuple[VerificationArtifact, ...]:
        """Return one immutable verification artifact per evidence item."""
        return tuple(self.verify_evidence(record.id, evidence, retrieval_artifact) for evidence in record.evidence)

    def verify_evidence(
        self,
        app_id: int,
        evidence: Evidence,
        retrieval_artifact: RetrievalArtifact,
    ) -> VerificationArtifact:
        source = next(
            (
                candidate
                for candidate in retrieval_artifact.fetched_sources
                if canonicalize_url(candidate.final_url or candidate.requested_url) == canonicalize_url(evidence.url)
            ),
            None,
        )
        if source is None or not source.extracted_text:
            verification = _unverifiable(app_id, evidence, "The cited URL has no saved cleaned source text.")
            return VerificationArtifact(app_id, evidence.field, evidence.claim, evidence.url, None, None, None, verification)

        context = "\n".join(
            (
                f"CLAIM_FIELD: {evidence.field}",
                f"CLAIM: {evidence.claim}",
                f"SOURCE_URL: {source.final_url or source.requested_url}",
                f"SOURCE_TITLE: {source.title or ''}",
                "CLEAN_SOURCE_TEXT:",
                source.extracted_text[:12_000],
            )
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                store=False,
                instructions=VERIFIER_INSTRUCTIONS,
                input=context,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "claim_verification",
                        "strict": True,
                        "schema": openai_strict_json_schema(ClaimVerification),
                    }
                },
            )
        except Exception as error:
            raise EvidenceVerificationError(f"Responses API request failed: {error}") from error

        raw_output = getattr(response, "output_text", "")
        if not raw_output:
            raise EvidenceVerificationError("Responses API returned no output_text for claim verification.")
        try:
            payload = json.loads(raw_output)
            # These values are pipeline inputs, never model-controlled identity.
            payload.update(
                {
                    "app_id": app_id,
                    "field": evidence.field,
                    "claim": evidence.claim,
                    "source_url": evidence.url,
                }
            )
            verification = ClaimVerification.model_validate(payload)
        except Exception as error:
            raise EvidenceVerificationError(f"Verifier output did not validate as ClaimVerification: {error}") from error

        return VerificationArtifact(
            app_id=app_id,
            field=evidence.field,
            claim=evidence.claim,
            source_url=evidence.url,
            model=self.model,
            response_id=getattr(response, "id", None),
            raw_output=raw_output,
            verification=verification,
        )


def verification_artifact_path(app_id: int, evidence_index: int, log_dir: Path = LOG_DIR) -> Path:
    return log_dir / "verification" / f"{app_id:03d}_{evidence_index:02d}.json"


def save_verification_artifacts(artifacts: tuple[VerificationArtifact, ...], log_dir: Path = LOG_DIR) -> tuple[Path, ...]:
    paths: list[Path] = []
    for index, artifact in enumerate(artifacts, start=1):
        path = verification_artifact_path(artifact.app_id, index, log_dir)
        write_json(path, artifact)
        paths.append(path)
    return tuple(paths)
