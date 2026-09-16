"""Resumable, bounded-concurrency orchestration for the 100-app research run."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from composio_research.apps import AppEntry
from composio_research.config import LOG_DIR, PASS1_DIR, PASS2_DIR, Settings
from composio_research.evidence_verifier import EvidenceVerifier, save_verification_artifacts
from composio_research.research import ResearchExtractor, save_research_artifact
from composio_research.retrieval import Fetcher, retrieval_artifact_from_dict, retrieval_artifact_path, retrieve_plan, save_retrieval_artifact
from composio_research.retry_policy import execute_retry, retry_tasks
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
            finally:
                fetcher.close()
                close = getattr(provider, "close", None)
                if callable(close):
                    close()
            save_retrieval_artifact(retrieval, log_dir)
            stage = "extract_pass1"
            record, artifact = ResearchExtractor(settings).extract(entry, retrieval, pass_number=1)
            write_json(pass1_path, record)
            save_research_artifact(artifact, log_dir)

        stage = "load_retrieval"
        retrieval = retrieval_artifact_from_dict(read_json(retrieval_path))
        stage = "verify"
        verifications = EvidenceVerifier(settings).verify(record, retrieval)
        save_verification_artifacts(verifications, log_dir)

        stage = "targeted_retry"
        if not retry_tasks(record, verifications):
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
        return AppRunResult(entry.id, entry.name, "pass2_complete", f"Retried {len(retry.tasks)} field(s).")
    except Exception as error:
        _save_error(entry, stage, error, log_dir)
        return AppRunResult(entry.id, entry.name, "error", f"{stage}: {type(error).__name__}: {error}")


def run_batch(entries: Iterable[AppEntry], settings: Settings, *, max_concurrency: int | None = None) -> tuple[AppRunResult, ...]:
    """Run entries with bounded concurrency; one app error never stops another app."""
    selected = tuple(entries)
    workers = max_concurrency or settings.max_concurrency
    if workers < 1:
        raise ValueError("max_concurrency must be at least 1.")
    results: list[AppRunResult] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research") as executor:
        futures = {executor.submit(run_one, entry, settings): entry for entry in selected}
        for future in as_completed(futures):
            results.append(future.result())
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
    missing = expected - pass1_ids - error_ids
    return CompletenessReport(
        expected_ids=tuple(sorted(expected)),
        pass1_ids=tuple(sorted(pass1_ids)),
        pass2_ids=tuple(sorted(pass2_ids)),
        terminal_error_ids=tuple(sorted(error_ids)),
        missing_ids=tuple(sorted(missing)),
    )
