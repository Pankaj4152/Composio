"""Render the self-contained HTML case study from generated analysis artifacts."""

from composio_research.config import PROJECT_ROOT
from composio_research.report import build_report


def main() -> None:
    print({"output": str(build_report(output_path=PROJECT_ROOT / "index.html"))})


if __name__ == "__main__":
    main()
