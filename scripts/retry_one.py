"""Perform a targeted, frozen pass-two retry for one verified pass-one record."""

import argparse

from composio_research.apps import APPS
from composio_research.config import LOG_DIR, PASS1_DIR, load_settings
from composio_research.evidence_verifier import EvidenceVerifier, save_verification_artifacts
from composio_research.research import ResearchExtractor
from composio_research.retrieval import Fetcher, retrieval_artifact_from_dict, retrieval_artifact_path
from composio_research.retry_policy import execute_retry
from composio_research.schema import AppRecord
from composio_research.search import create_search_provider
from composio_research.serialization import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_id", type=int)
    args = parser.parse_args()
    entry = next((app for app in APPS if app.id == args.app_id), None)
    if entry is None:
        raise SystemExit(f"Unknown app id: {args.app_id}")

    settings = load_settings()
    record = AppRecord.model_validate(read_json(PASS1_DIR / f"{entry.id:03d}.json"))
    original = retrieval_artifact_from_dict(read_json(retrieval_artifact_path(entry.id, LOG_DIR)))
    verifier = EvidenceVerifier(settings)
    verifications = verifier.verify(record, original)
    save_verification_artifacts(verifications)
    fetcher = Fetcher(timeout_seconds=settings.request_timeout_seconds)
    try:
        result = execute_retry(
            entry, record, verifications, original, ResearchExtractor(settings), fetcher, create_search_provider(settings)
        )
    finally:
        fetcher.close()
    print(result)


if __name__ == "__main__":
    main()
