"""Verify every cited claim in one accepted pass-one record."""

import argparse

from composio_research.apps import APPS
from composio_research.config import LOG_DIR, PASS1_DIR, load_settings
from composio_research.evidence_verifier import EvidenceVerifier, save_verification_artifacts
from composio_research.retrieval import retrieval_artifact_from_dict, retrieval_artifact_path
from composio_research.schema import AppRecord
from composio_research.serialization import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_id", type=int)
    args = parser.parse_args()

    entry = next((app for app in APPS if app.id == args.app_id), None)
    if entry is None:
        raise SystemExit(f"Unknown app id: {args.app_id}")
    record = AppRecord.model_validate(read_json(PASS1_DIR / f"{entry.id:03d}.json"))
    retrieval = retrieval_artifact_from_dict(read_json(retrieval_artifact_path(entry.id, LOG_DIR)))
    artifacts = EvidenceVerifier(load_settings()).verify(record, retrieval)
    paths = save_verification_artifacts(artifacts)
    counts: dict[str, int] = {}
    for artifact in artifacts:
        status = artifact.verification.status.value
        counts[status] = counts.get(status, 0) + 1
    print({"app": entry.name, "claims": len(artifacts), "status_counts": counts, "artifacts": [str(path) for path in paths]})


if __name__ == "__main__":
    main()
