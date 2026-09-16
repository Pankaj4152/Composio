"""Fetch and log a small direct-hint retrieval sample without web search."""

import argparse

from composio_research.apps import APPS
from composio_research.retrieval import Fetcher, retrieve_plan, save_retrieval_artifact
from composio_research.source_planner import plan_research


DEFAULT_APPS = ("Slack", "Shopify", "GitHub", "Google Ads", "PitchBook")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", nargs="+", default=list(DEFAULT_APPS))
    args = parser.parse_args()

    requested_names = set(args.apps)
    selected_apps = [app for app in APPS if app.name in requested_names]
    missing_names = requested_names - {app.name for app in selected_apps}
    if missing_names:
        parser.error(f"Unknown app names: {', '.join(sorted(missing_names))}")

    fetcher = Fetcher(timeout_seconds=20, max_attempts=2, backoff_seconds=0.25)
    try:
        for app in selected_apps:
            artifact = retrieve_plan(plan_research(app), fetcher)
            save_retrieval_artifact(artifact)
            source = artifact.fetched_sources[0] if artifact.fetched_sources else None
            if source is None:
                print(f"{app.name}: no direct source candidate")
                continue
            print(
                f"{app.name}: {source.status.value}; final={source.final_url}; "
                f"title={source.title!r}; chars={len(source.extracted_text or '')}"
            )
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
