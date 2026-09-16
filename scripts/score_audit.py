"""Validate completed human audit records and write transparent accuracy metrics."""

import argparse
from pathlib import Path

from composio_research.audit_metrics import load_completed_audits, save_scorecard, score_audits, validate_completed_audits
from composio_research.human_audit import load_pass2_records, load_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("completed_audit_json", type=Path)
    args = parser.parse_args()
    records = load_completed_audits(args.completed_audit_json)
    # Keep both freezes available. A pass-one audit must be checked against
    # pass one, not replaced by its later targeted retry in final analysis.
    validate_completed_audits(records, load_records() + load_pass2_records())
    output = save_scorecard(score_audits(records))
    print({"completed_records": len(records), "output": str(output)})


if __name__ == "__main__":
    main()
