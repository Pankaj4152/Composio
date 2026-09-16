"""Create one schema-validated research record from a saved retrieval artifact."""

import argparse

from composio_research.apps import APPS
from composio_research.config import LOG_DIR, PASS1_DIR, load_settings
from composio_research.research import ResearchExtractionError, ResearchExtractor, save_research_artifact
from composio_research.retrieval import retrieval_artifact_from_dict
from composio_research.serialization import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_name")
    parser.add_argument("--pass", dest="pass_number", type=int, default=1)
    args = parser.parse_args()

    entry = next((app for app in APPS if app.name == args.app_name), None)
    if entry is None:
        parser.error(f"Unknown app: {args.app_name}")
    retrieval_path = LOG_DIR / "retrieval" / f"{entry.id:03d}.json"
    if not retrieval_path.exists():
        parser.error(f"No retrieval artifact at {retrieval_path}. Run retrieval first.")

    retrieval_artifact = retrieval_artifact_from_dict(read_json(retrieval_path))
    try:
        record, artifact = ResearchExtractor(load_settings()).extract(
            entry, retrieval_artifact, pass_number=args.pass_number
        )
    except ResearchExtractionError as error:
        if error.artifact is not None:
            save_research_artifact(error.artifact)
        raise
    output_path = PASS1_DIR / f"{entry.id:03d}.json"
    write_json(output_path, record)
    save_research_artifact(artifact)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
