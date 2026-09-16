"""Resumable, bounded-concurrency orchestration for the 100-app research run."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Callable, Iterable

from composio_research.apps import AppEntry
from composio_research.config import LOG_DIR, PASS1_DIR, PASS2_DIR, Settings
from composio_research.evidence_verifier import EvidenceVerifier, save_verification_artifacts
from composio_research.research import ResearchExtractionError, ResearchExtractor, save_research_artifact
from composio_research.retrieval import Fetcher, retrieval_artifact_from_dict, retrieval_artifact_path, retrieve_plan, save_retrieval_artifact
from composio_research.retry_policy import RetryTask, execute_retry, retry_context, retry_plan, retry_tasks, targeted_query
from composio_research.schema import AppRecord, TerminalErrorRecord
from composio_research.search import create_search_provider
from composio_research.serialization import read_json, write_json
from composio_research.source_planner import plan_research


ERROR_DIR_NAME = "terminal_errors"


@dataclass(frozen=True, slots=True)
class AppRunResult:
    app_id: int
    app_name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    expected_ids: tuple[int, ...]
    pass1_ids: tuple[int, ...]
    pass2_ids: tuple[int, ...]
    terminal_error_ids: tuple[int, ...]
    unresolved_error_ids: tuple[int, ...]
    resolved_error_ids: tuple[int, ...]
    missing_ids: tuple[int, ...]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _record_path(directory: Path, app_id: int) -> Path:
    return directory / f"{app_id:03d}.json"


def _error_path(log_dir: Path, app_id: int) -> Path:
    return log_dir / ERROR_DIR_NAME / f"{app_id:03d}.json"


def _save_error(entry: AppEntry, stage: str, error: Exception, log_dir: Path) -> None:
    write_json(
        _error_path(log_dir, entry.id),
        TerminalErrorRecord(
            app_id=entry.id,
            app_name=entry.name,
            stage=stage,
            error_type=type(error).__name__,
            message=str(error),
            created_at=_utc_now(),
        ),
    )


def _resolve_error(entry: AppEntry, log_dir: Path) -> None:
    """Archive—not delete—an old terminal error after the app finishes successfully."""
    current = _error_path(log_dir, entry.id)
    if not current.exists():
        return
    archived = log_dir / "resolved_errors" / current.name
    archived.parent.mkdir(parents=True, exist_ok=True)
    current.replace(archived)


def _initial_retry_tasks(entry: AppEntry, error: ResearchExtractionError) -> tuple[RetryTask, ...]:
    fields = sorted(set(re.findall(r"([a-z_]+): Specific claim", str(error))))
    return tuple(
        RetryTask(entry.id, field, "Initial extraction lacked required claim-level evidence.", targeted_query(entry.name, field))
        for field in fields
    )


def run_one(
    entry: AppEntry,
    settings: Settings,
    *,
    pass1_dir: Path = PASS1_DIR,
    pass2_dir: Path = PASS2_DIR,
    log_dir: Path = LOG_DIR,
) -> AppRunResult:
    """Run or resume one app; failure is isolated and persisted for batch recovery."""
    stage = "load_pass1"
    try:
        pass1_path = _record_path(pass1_dir, entry.id)
        retrieval_path = retrieval_artifact_path(entry.id, log_dir)
        if pass1_path.exists():
            record = AppRecord.model_validate(read_json(pass1_path))
        else:
            stage = "retrieve_pass1"
            provider = create_search_provider(settings)
            fetcher = Fetcher(timeout_seconds=settings.request_timeout_seconds)
            try:
                retrieval = retrieve_plan(plan_research(entry), fetcher, provider)
                save_retrieval_artifact(retrieval, log_dir)
                stage = "extract_pass1"
                extractor = ResearchExtractor(settings)
                try:
                    record, artifact = extractor.extract(entry, retrieval, pass_number=1)
                except ResearchExtractionError as error:
                    tasks = _initial_retry_tasks(entry, error)
                    if not tasks:
                        raise
                    stage = "targeted_retry_pass1"
                    retrieval = retrieve_plan(retry_plan(retrieval.plan, tasks), fetcher, provider, max_candidates=8)
                    write_json(log_dir / "retrieval" / f"{entry.id:03d}_pass1_retry.json", retrieval)
                    record, artifact = extractor.extract(entry, retrieval, pass_number=1, retry_context=retry_context(tasks))
                    save_retrieval_artifact(retrieval, log_dir)
            finally:
                fetcher.close()
                close = getattr(provider, "close", None)
                if callable(close):
                    close()
            write_json(pass1_path, record)
            save_research_artifact(artifact, log_dir)

        stage = "load_retrieval"
        retrieval = retrieval_artifact_from_dict(read_json(retrieval_path))
        stage = "verify"
        verifications = EvidenceVerifier(settings).verify(record, retrieval)
        save_verification_artifacts(verifications, log_dir)

        stage = "targeted_retry"
        if not retry_tasks(record, verifications):
            _resolve_error(entry, log_dir)
            return AppRunResult(entry.id, entry.name, "verified", "No retry trigger fired.")
        provider = create_search_provider(settings)
        fetcher = Fetcher(timeout_seconds=settings.request_timeout_seconds)
        try:
            retry = execute_retry(
                entry,
                record,
                verifications,
                retrieval,
                ResearchExtractor(settings),
                fetcher,
                provider,
                log_dir=log_dir,
                pass2_dir=pass2_dir,
            )
        finally:
            fetcher.close()
            close = getattr(provider, "close", None)
            if callable(close):
                close()
        _resolve_error(entry, log_dir)
        return AppRunResult(entry.id, entry.name, "pass2_complete", f"Retried {len(retry.tasks)} field(s).")
    except Exception as error:
        _save_error(entry, stage, error, log_dir)
        return AppRunResult(entry.id, entry.name, "error", f"{stage}: {type(error).__name__}: {error}")


def run_batch(
    entries: Iterable[AppEntry],
    settings: Settings,
    *,
    max_concurrency: int | None = None,
    on_result: Callable[[int, int, AppRunResult], None] | None = None,
) -> tuple[AppRunResult, ...]:
    """Run entries with bounded concurrency; one app error never stops another app."""
    selected = tuple(entries)
    workers = max_concurrency or settings.max_concurrency
    if workers < 1:
        raise ValueError("max_concurrency must be at least 1.")
    results: list[AppRunResult] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research") as executor:
        futures = {executor.submit(run_one, entry, settings): entry for entry in selected}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if on_result is not None:
                on_result(len(results), len(selected), result)
    return tuple(sorted(results, key=lambda result: result.app_id))


def _valid_ids(directory: Path, model: type[AppRecord | TerminalErrorRecord]) -> set[int]:
    ids: set[int] = set()
    if not directory.exists():
        return ids
    for path in directory.glob("*.json"):
        try:
            value = model.model_validate(read_json(path))
        except Exception:
            continue
        ids.add(value.id if isinstance(value, AppRecord) else value.app_id)
    return ids


def validate_completeness(
    entries: Iterable[AppEntry],
    *,
    pass1_dir: Path = PASS1_DIR,
    pass2_dir: Path = PASS2_DIR,
    log_dir: Path = LOG_DIR,
) -> CompletenessReport:
    """Report every expected app ID not represented by a valid record or terminal error."""
    expected = {entry.id for entry in entries}
    pass1_ids = _valid_ids(pass1_dir, AppRecord)
    pass2_ids = _valid_ids(pass2_dir, AppRecord)
    error_ids = _valid_ids(log_dir / ERROR_DIR_NAME, TerminalErrorRecord)
    unresolved_errors = error_ids - pass1_ids
    resolved_errors = error_ids & pass1_ids
    missing = expected - pass1_ids - unresolved_errors
    return CompletenessReport(
        expected_ids=tuple(sorted(expected)),
        pass1_ids=tuple(sorted(pass1_ids)),
        pass2_ids=tuple(sorted(pass2_ids)),
        terminal_error_ids=tuple(sorted(error_ids)),
        unresolved_error_ids=tuple(sorted(unresolved_errors)),
        resolved_error_ids=tuple(sorted(resolved_errors)),
        missing_ids=tuple(sorted(missing)),
    )
