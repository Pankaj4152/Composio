"""Create blank, deterministic external human-audit tasks from frozen pass-one data."""

import argparse

from composio_research.human_audit import build_audit_templates, load_records, save_audit_templates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--representative-size", type=int, default=12)
    parser.add_argument("--challenge-size", type=int, default=5)
    args = parser.parse_args()
    records = load_records()
    if not records:
        raise SystemExit("No frozen pass-one records exist; run research before creating an audit sample.")
    output = save_audit_templates(build_audit_templates(
        records, representative_size=args.representative_size, challenge_size=args.challenge_size
    ))
    print({"records_available": len(records), "output": str(output)})


if __name__ == "__main__":
    main()
