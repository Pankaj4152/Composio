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
        print(report)
        return
    results = run_batch(selected, load_settings(), max_concurrency=args.max_concurrency)
    write_json(LOG_DIR / "runs" / "latest.json", results)
    report = validate_completeness(APPS)
    write_json(LOG_DIR / "runs" / "completeness.json", report)
    print({"completed": len(results), "errors": sum(result.status == "error" for result in results), "missing_ids": report.missing_ids})


if __name__ == "__main__":
    main()
