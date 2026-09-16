"""Validate completed human audit records and write transparent accuracy metrics."""

import argparse
from pathlib import Path

from composio_research.analysis import load_final_records
from composio_research.audit_metrics import load_completed_audits, save_scorecard, score_audits, validate_completed_audits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed_audit_json", type=Path)
    args = parser.parse_args()
    records = load_completed_audits(args.completed_audit_json)
    validate_completed_audits(records, load_final_records())
    output = save_scorecard(score_audits(records))
    print({"completed_records": len(records), "output": str(output)})


if __name__ == "__main__":
    main()
