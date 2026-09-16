"""Render the self-contained HTML case study from generated analysis artifacts."""

from composio_research.report import build_report


def main() -> None:
    print({"output": str(build_report())})


if __name__ == "__main__":
    main()
