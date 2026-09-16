"""Structured, evidence-constrained one-app research extraction."""

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from composio_research.apps import AppEntry
from composio_research.config import LOG_DIR, Settings
from composio_research.retrieval import RetrievalArtifact, canonicalize_url
from composio_research.schema import (
    ApiSurface,
    AppRecord,
    BlockerType,
    BuildabilityVerdict,
    CredentialAccess,
    MCPStatus,
    AuthMethod,
)
from composio_research.serialization import write_json


SYSTEM_INSTRUCTIONS = """You are a precise integration-research analyst.
Return one JSON object that conforms exactly to the supplied AppRecord schema.

Use only the provided source context. Never invent URLs, source excerpts, API
facts, credential gates, MCP servers, or Composio coverage. Evidence must cite
a URL present in the source context and must be attached to the exact field and
claim it supports. If evidence is inadequate, use the schema's UNKNOWN/UNCLEAR
values, lower confidence, and explain the limitation in agent_notes.

Do not confuse product signup/free tiers with API credential access. Distinguish
admin approval, app review, enterprise plans, partner-only access, and contact
sales. An MCP server is real only when the supplied source documents it. Derive
buildability from the recorded API and access facts; do not rank the company.
"""


class ResponsesClient(Protocol):
    class responses:  # type: ignore[valid-type]
        @staticmethod
        def create(**kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class ConsistencyIssue:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    app_id: int
    app_name: str
    pass_number: int
    model: str
    response_id: str | None
    raw_output: str
    consistency_issues: tuple[ConsistencyIssue, ...]


class ResearchExtractionError(RuntimeError):
    """The model response cannot be used as a valid research record."""

    def __init__(self, message: str, *, artifact: ResearchArtifact | None = None) -> None:
        super().__init__(message)
        self.artifact = artifact


def build_research_context(entry: AppEntry, artifact: RetrievalArtifact, *, max_chars_per_source: int = 12_000) -> str:
    """Prepare only clean fetched text and traceable source metadata for the model."""
    source_sections: list[str] = []
    for index, source in enumerate(artifact.fetched_sources, start=1):
        if source.extracted_text is None or source.final_url is None:
            continue
        source_sections.append(
            "\n".join(
                (
                    f"SOURCE {index}",
                    f"URL: {source.final_url}",
                    f"TITLE: {source.title or ''}",
                    f"TYPE: {source.source_type.value}",
                    f"OFFICIAL_DOMAIN: {source.is_official_domain}",
                    f"RELEVANCE_SCORE: {source.relevance_score}",
                    f"HUMAN_REVIEW_FLAG: {source.requires_human_review}",
                    "CLEAN_TEXT:",
                    source.extracted_text[:max_chars_per_source],
                )
            )
        )

    return "\n\n".join(
        (
            f"APP: {entry.name}",
            f"CATEGORY: {entry.category}",
            f"ASSIGNMENT_HINT: {entry.hint}",
            "\nSOURCES:\n" + ("\n\n".join(source_sections) or "No usable fetched sources."),
        )
    )


def openai_strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Adapt Pydantic JSON Schema to OpenAI strict Structured Outputs rules.

    Pydantic treats nullable/defaulted fields as optional. OpenAI requires every
    object property in a strict schema to be required; nullability remains in
    the property's type definition, so optional values can still be ``null``.
    """
    schema = json.loads(json.dumps(model.model_json_schema()))

    def visit(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
            node.pop("default", None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema


def validate_record_consistency(record: AppRecord, artifact: RetrievalArtifact) -> list[ConsistencyIssue]:
    """Apply deterministic rules that should not be delegated to the model."""
    issues: list[ConsistencyIssue] = []
    if record.api_surface == ApiSurface.NONE_PUBLIC and record.buildability_verdict == BuildabilityVerdict.BUILD_NOW:
        issues.append(ConsistencyIssue("buildability_verdict", "A non-public API cannot be BUILD_NOW."))
    if record.credential_access in {CredentialAccess.PARTNER_ONLY, CredentialAccess.CONTACT_SALES} and record.buildability_verdict == BuildabilityVerdict.BUILD_NOW:
        issues.append(ConsistencyIssue("buildability_verdict", "Commercially gated credentials cannot normally be BUILD_NOW."))
    if record.mcp_status not in {MCPStatus.NONE_FOUND, MCPStatus.UNKNOWN} and not record.mcp_source_url:
        issues.append(ConsistencyIssue("mcp_source_url", "A discovered MCP status requires a source URL."))
    if record.blocker_type == BlockerType.NO_PUBLIC_API and record.api_surface != ApiSurface.NONE_PUBLIC:
        issues.append(ConsistencyIssue("blocker_type", "NO_PUBLIC_API must align with api_surface=none_public."))

    allowed_urls = {
        canonicalize_url(source.final_url or source.requested_url)
        for source in artifact.fetched_sources
        if source.status.value == "fetched"
    }
    for evidence in record.evidence:
        if canonicalize_url(evidence.url) not in allowed_urls:
            issues.append(
                ConsistencyIssue(
                    "evidence.url",
                    f"Evidence URL was not included in the fetched source context: {evidence.url}",
                )
            )
    issues.extend(critical_evidence_issues(record))
    return issues


def critical_evidence_issues(record: AppRecord) -> list[ConsistencyIssue]:
    """Require claim-level support for specific facts used in operations decisions."""
    evidence_fields = {evidence.field for evidence in record.evidence}
    required_fields: list[str] = []
    if any(method != AuthMethod.UNKNOWN for method in record.auth_methods):
        required_fields.append("auth_methods")
    if record.credential_access != CredentialAccess.UNCLEAR:
        required_fields.append("credential_access")
    if record.api_surface != ApiSurface.UNKNOWN:
        required_fields.append("api_surface")
    if record.api_breadth.value != "unknown":
        required_fields.append("api_breadth")
    if record.mcp_status != MCPStatus.UNKNOWN:
        required_fields.append("mcp_status")
    # Buildability has no UNKNOWN state; every verdict is an operational claim.
    required_fields.append("buildability_verdict")
    if record.blocker_type != BlockerType.NONE:
        required_fields.append("blocker_type")

    return [
        ConsistencyIssue(field, f"Specific claim '{field}' has no claim-level evidence.")
        for field in required_fields
        if field not in evidence_fields
    ]


class ResearchExtractor:
    """One-app OpenAI Responses API extractor with strict post-validation."""

    def __init__(self, settings: Settings, *, client: ResponsesClient | None = None) -> None:
        if settings.openai_api_key is None and client is None:
            raise ResearchExtractionError("OPENAI_API_KEY is required for structured research extraction.")
        self.model = settings.openai_model
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=0)
        self.client = client

    def extract(self, entry: AppEntry, retrieval_artifact: RetrievalArtifact, *, pass_number: int = 1) -> tuple[AppRecord, ResearchArtifact]:
        context = build_research_context(entry, retrieval_artifact)
        try:
            response = self.client.responses.create(
                model=self.model,
                store=False,
                instructions=SYSTEM_INSTRUCTIONS,
                input=context,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "app_research_record",
                        "strict": True,
                        "schema": openai_strict_json_schema(AppRecord),
                    }
                },
            )
        except Exception as error:
            raise ResearchExtractionError(f"Responses API request failed: {error}") from error
        raw_output = getattr(response, "output_text", "")
        if not raw_output:
            raise ResearchExtractionError("Responses API returned no output_text.")

        base_artifact = ResearchArtifact(
            app_id=entry.id,
            app_name=entry.name,
            pass_number=pass_number,
            model=self.model,
            response_id=getattr(response, "id", None),
            raw_output=raw_output,
            consistency_issues=(),
        )

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as error:
            raise ResearchExtractionError(
                f"Model output was not valid JSON: {error.msg}", artifact=base_artifact
            ) from error

        # Identity and pass number come from the source dataset/pipeline, not the model.
        payload.update(
            {
                "id": entry.id,
                "app": entry.name,
                "category": entry.category,
                "hint": entry.hint,
                "pass_number": pass_number,
            }
        )
        try:
            record = AppRecord.model_validate(payload)
        except Exception as error:
            raise ResearchExtractionError(
                f"Model output did not validate as AppRecord: {error}", artifact=base_artifact
            ) from error

        issues = tuple(validate_record_consistency(record, retrieval_artifact))
        research_artifact = replace(base_artifact, consistency_issues=issues)
        if issues:
            formatted_issues = "; ".join(f"{issue.field}: {issue.message}" for issue in issues)
            raise ResearchExtractionError(
                f"Record failed deterministic consistency checks: {formatted_issues}", artifact=research_artifact
            )
        return record, research_artifact


def research_artifact_path(app_id: int, pass_number: int, log_dir: Path = LOG_DIR) -> Path:
    return log_dir / "research" / f"{app_id:03d}_pass{pass_number}.json"


def save_research_artifact(artifact: ResearchArtifact, log_dir: Path = LOG_DIR) -> Path:
    path = research_artifact_path(artifact.app_id, artifact.pass_number, log_dir)
    write_json(path, artifact)
    return path
