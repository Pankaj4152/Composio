"""Run or resume the evidence-verified research pipeline for selected assignment apps."""

import argparse

from composio_research.apps import APPS
from composio_research.batch import run_batch, validate_completeness
from composio_research.config import LOG_DIR, load_settings
from composio_research.serialization import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", type=int, action="append", dest="app_ids", help="Repeat to run specific IDs only.")
    parser.add_argument("--max-concurrency", type=int, help="Override MAX_CONCURRENCY for this invocation.")
    parser.add_argument("--check-only", action="store_true", help="Report completeness without external requests.")
    args = parser.parse_args()
    selected = tuple(app for app in APPS if not args.app_ids or app.id in set(args.app_ids))
    if args.app_ids and len(selected) != len(set(args.app_ids)):
        raise SystemExit("One or more --app-id values are invalid.")
    if args.check_only:
        report = validate_completeness(APPS)
        print(f"pass1={len(report.pass1_ids)}, pass2={len(report.pass2_ids)}, unresolved_errors={len(report.unresolved_error_ids)}, resolved_error_artifacts={len(report.resolved_error_ids)}, missing={len(report.missing_ids)}")
        if report.unresolved_error_ids:
            print(f"Unresolved error IDs: {report.unresolved_error_ids}")
        return
    settings = load_settings()
    workers = args.max_concurrency or settings.max_concurrency
    print(f"Starting {len(selected)} app(s) with max concurrency={workers}. Existing frozen records will be resumed.", flush=True)

    def progress(completed: int, total: int, result) -> None:
        print(f"[{completed}/{total}] {result.app_name} ({result.app_id:03d}) — {result.status}: {result.detail}", flush=True)

    results = run_batch(selected, settings, max_concurrency=args.max_concurrency, on_result=progress)
    write_json(LOG_DIR / "runs" / "latest.json", results)
    report = validate_completeness(APPS)
    write_json(LOG_DIR / "runs" / "completeness.json", report)
    errors = sum(result.status == "error" for result in results)
    print(f"Finished. processed={len(results)}, errors={errors}, pass1={len(report.pass1_ids)}, pass2={len(report.pass2_ids)}, unresolved_errors={len(report.unresolved_error_ids)}, missing_ids={len(report.missing_ids)}", flush=True)
    if report.missing_ids:
        print(f"Missing IDs: {report.missing_ids}", flush=True)


if __name__ == "__main__":
    main()
