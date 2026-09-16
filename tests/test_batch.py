"""Tests for terminal-error accounting and completeness validation."""

from composio_research.apps import APPS
from composio_research.batch import AppRunResult, run_batch, validate_completeness
from composio_research.config import Settings
from composio_research.schema import (
    ApiBreadth,
    ApiSurface,
    AppRecord,
    AuthMethod,
    BlockerType,
    BuildabilityVerdict,
    CredentialAccess,
    MCPStatus,
    TerminalErrorRecord,
)
from composio_research.serialization import write_json


def make_record() -> AppRecord:
    entry = APPS[20]
    return AppRecord(
        id=entry.id, app=entry.name, category=entry.category, hint=entry.hint, one_liner="Messaging app.",
        auth_methods=[AuthMethod.UNKNOWN], credential_access=CredentialAccess.UNCLEAR,
        api_surface=ApiSurface.UNKNOWN, api_breadth=ApiBreadth.UNKNOWN, mcp_status=MCPStatus.UNKNOWN,
        buildability_verdict=BuildabilityVerdict.BUILD_WITH_FRICTION, blocker_type=BlockerType.UNCLEAR_DOCS,
        overall_confidence=0.2, pass_number=1,
    )


def test_completeness_reports_missing_and_terminal_error_ids(tmp_path) -> None:
    pass1 = tmp_path / "pass1"
    pass2 = tmp_path / "pass2"
    logs = tmp_path / "logs"
    write_json(pass1 / "021.json", make_record())
    write_json(
        logs / "terminal_errors" / "041.json",
        TerminalErrorRecord(
            app_id=41, app_name="Shopify", stage="extract_pass1", error_type="TimeoutError", message="timed out", created_at="2026-01-01T00:00:00+00:00"
        ),
    )

    report = validate_completeness((APPS[20], APPS[40], APPS[60]), pass1_dir=pass1, pass2_dir=pass2, log_dir=logs)

    assert report.pass1_ids == (21,)
    assert report.terminal_error_ids == (41,)
    assert report.missing_ids == (61,)


def test_batch_reports_each_completed_result_to_progress_callback(monkeypatch) -> None:
    import composio_research.batch as batch

    monkeypatch.setattr(batch, "run_one", lambda entry, settings, **kwargs: AppRunResult(entry.id, entry.name, "verified", "done"))
    progress = []
    results = run_batch(APPS[:2], Settings(_env_file=None), max_concurrency=1, on_result=lambda done, total, result: progress.append((done, total, result.id if hasattr(result, 'id') else result.app_id)))

    assert len(results) == 2
    assert progress == [(1, 2, 1), (2, 2, 2)]
