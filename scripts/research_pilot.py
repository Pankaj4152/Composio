"""Run the five-app research-extraction pilot from saved retrieval artifacts."""

import argparse

from composio_research.apps import APPS
from composio_research.config import LOG_DIR, PASS1_DIR, load_settings
from composio_research.research import ResearchExtractionError, ResearchExtractor, save_research_artifact
from composio_research.retrieval import retrieval_artifact_from_dict
from composio_research.serialization import read_json, write_json


PILOT_APPS = ("Slack", "Shopify", "GitHub", "Google Ads", "PitchBook")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Replace an existing frozen pass-one record.")
    args = parser.parse_args()
    extractor = ResearchExtractor(load_settings())
    summary: list[dict[str, str]] = []
    for app_name in PILOT_APPS:
        entry = next(app for app in APPS if app.name == app_name)
        retrieval_path = LOG_DIR / "retrieval" / f"{entry.id:03d}.json"
        output_path = PASS1_DIR / f"{entry.id:03d}.json"
        if output_path.exists() and not args.force:
            summary.append({"app": app_name, "status": "preserved", "detail": "existing frozen pass-one record"})
            continue
        if not retrieval_path.exists():
            summary.append({"app": app_name, "status": "skipped", "detail": "missing retrieval artifact"})
            continue
        try:
            retrieval_artifact = retrieval_artifact_from_dict(read_json(retrieval_path))
            record, artifact = extractor.extract(entry, retrieval_artifact)
            write_json(output_path, record)
            save_research_artifact(artifact)
            summary.append({"app": app_name, "status": "accepted", "detail": "validated record written"})
        except ResearchExtractionError as error:
            if error.artifact is not None:
                save_research_artifact(error.artifact)
            summary.append({"app": app_name, "status": "rejected", "detail": str(error)})

    write_json(LOG_DIR / "research" / "pilot_summary.json", summary)
    for row in summary:
        print(f"{row['app']}: {row['status']} — {row['detail']}")


if __name__ == "__main__":
    main()
