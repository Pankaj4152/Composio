"""Build machine-readable Product Ops analysis from frozen pass-one/two records."""

from composio_research.analysis import analyze, load_final_records, save_analysis


def main() -> None:
    records = load_final_records()
    if not records:
        raise SystemExit("No frozen records exist; run research before analysis.")
    output = save_analysis(analyze(records))
    print({"records_analyzed": len(records), "output": str(output)})


if __name__ == "__main__":
    main()
