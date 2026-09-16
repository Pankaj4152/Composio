"""Generate data-backed Product Ops findings from frozen research records."""

from composio_research.insights import build_insights_from_frozen_records, save_insights


def main() -> None:
    report = build_insights_from_frozen_records()
    if report.record_count == 0:
        raise SystemExit("No frozen records exist; run research before generating insights.")
    output = save_insights(report)
    print({"records_analyzed": report.record_count, "findings": len(report.findings), "output": str(output)})


if __name__ == "__main__":
    main()
