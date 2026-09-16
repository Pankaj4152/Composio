"""Deterministic retry decisions and targeted second-pass research support."""

from dataclasses import dataclass, replace
from pathlib import Path

from composio_research.apps import AppEntry
from composio_research.config import LOG_DIR, PASS2_DIR
from composio_research.evidence_verifier import VerificationArtifact
from composio_research.research import ResearchArtifact, ResearchExtractor, save_research_artifact
from composio_research.retrieval import Fetcher, RetrievalArtifact, SearchProvider, retrieve_plan
from composio_research.schema import AppRecord, VerificationStatus
from composio_research.serialization import write_json
from composio_research.source_planner import PlannedQuery, ResearchPlan


CRITICAL_FIELDS = frozenset({
    "auth_methods", "credential_access", "api_surface", "api_breadth", "mcp_status", "buildability_verdict", "blocker_type",
})


@dataclass(frozen=True, slots=True)
class RetryTask:
    app_id: int
    field: str
    reason: str
    query: str


@dataclass(frozen=True, slots=True)
class RetryArtifact:
    app_id: int
    pass_number: int
    tasks: tuple[RetryTask, ...]
    retrieval_artifact_path: str | None
    research_artifact_path: str | None
    pass2_record_path: str | None


def retry_tasks(record: AppRecord, verifications: tuple[VerificationArtifact, ...], *, confidence_threshold: float = 0.75) -> tuple[RetryTask, ...]:
    """Produce de-duplicated, field-level research tasks from frozen pass-one output."""
    reasons: dict[str, list[str]] = {}
    if record.overall_confidence < confidence_threshold:
        reasons.setdefault("overall_confidence", []).append(f"overall confidence {record.overall_confidence:.2f} is below {confidence_threshold:.2f}")
    for artifact in verifications:
        verdict = artifact.verification
        if verdict.field in CRITICAL_FIELDS and verdict.status in {
            VerificationStatus.UNSUPPORTED,
            VerificationStatus.CONFLICTING,
            VerificationStatus.UNVERIFIABLE,
        }:
            reasons.setdefault(verdict.field, []).append(f"verification is {verdict.status.value}: {verdict.explanation}")

    tasks = []
    for field in sorted(reasons):
        query = targeted_query(record.app, field)
        tasks.append(RetryTask(record.id, field, "; ".join(reasons[field]), query))
    return tuple(tasks)


def targeted_query(app_name: str, field: str) -> str:
    """Use only evidence-oriented queries; never ask the search engine to decide a verdict."""
    topic = {
        "auth_methods": "API authentication OAuth API key",
        "credential_access": "developer credentials API access pricing approval",
        "api_surface": "developer API reference REST GraphQL",
        "api_breadth": "API reference endpoints resources",
        "mcp_status": "MCP server model context protocol",
        "buildability_verdict": "developer API authentication access",
        "blocker_type": "developer API access requirements limitations",
        "overall_confidence": "developer API authentication access documentation",
    }.get(field, "developer API documentation")
    return f"{app_name} {topic} official documentation"


def retry_plan(plan: ResearchPlan, tasks: tuple[RetryTask, ...]) -> ResearchPlan:
    """Append targeted query plans, retaining every original direct source and query."""
    added = tuple(PlannedQuery(query=task.query, purpose=f"Targeted retry for {task.field}") for task in tasks)
    return replace(plan, queries=plan.queries + added)


def retry_context(tasks: tuple[RetryTask, ...]) -> str:
    return "\n".join(
        f"- Field {task.field}: {task.reason}. Research this exact field with official evidence."
        for task in tasks
    )


def execute_retry(
    entry: AppEntry,
    record: AppRecord,
    verifications: tuple[VerificationArtifact, ...],
    original_retrieval: RetrievalArtifact,
    extractor: ResearchExtractor,
    fetcher: Fetcher,
    search_provider: SearchProvider | None,
    *,
    log_dir: Path = LOG_DIR,
    pass2_dir: Path = PASS2_DIR,
) -> RetryArtifact:
    """Perform one traceable pass-two extraction only when retry policy requires it."""
    tasks = retry_tasks(record, verifications)
    if not tasks:
        return RetryArtifact(entry.id, 2, (), None, None, None)
    retrieval = retrieve_plan(
        retry_plan(original_retrieval.plan, tasks),
        fetcher,
        search_provider,
        max_candidates=8,
    )
    # Do not overwrite pass-one evidence: pass two needs its own source set.
    retrieval_path = log_dir / "retrieval" / f"{entry.id:03d}_pass2.json"
    write_json(retrieval_path, retrieval)
    record2, research_artifact = extractor.extract(
        entry,
        retrieval,
        pass_number=2,
        retry_context=retry_context(tasks),
    )
    research_path = save_research_artifact(research_artifact, log_dir)
    record_path = pass2_dir / f"{entry.id:03d}.json"
    write_json(record_path, record2)
    artifact = RetryArtifact(
        entry.id,
        2,
        tasks,
        str(retrieval_path),
        str(research_path),
        str(record_path),
    )
    write_json(log_dir / "retry" / f"{entry.id:03d}.json", artifact)
    return artifact
