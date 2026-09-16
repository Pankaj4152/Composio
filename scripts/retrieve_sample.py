"""Fetch and log a small direct-hint retrieval sample without web search."""

import argparse

from composio_research.apps import APPS
from composio_research.config import load_settings
from composio_research.retrieval import Fetcher, retrieve_plan, save_retrieval_artifact
from composio_research.search import create_search_provider
from composio_research.source_planner import plan_research


DEFAULT_APPS = ("Slack", "Shopify", "GitHub", "Google Ads", "PitchBook")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", nargs="+", default=list(DEFAULT_APPS))
    parser.add_argument("--direct-only", action="store_true", help="Skip configured web search.")
    parser.add_argument("--per-query-limit", type=int, default=3)
    parser.add_argument("--max-candidates", type=int, default=6)
    args = parser.parse_args()

    requested_names = set(args.apps)
    selected_apps = [app for app in APPS if app.name in requested_names]
    missing_names = requested_names - {app.name for app in selected_apps}
    if missing_names:
        parser.error(f"Unknown app names: {', '.join(sorted(missing_names))}")

    settings = load_settings()
    search_provider = None if args.direct_only else create_search_provider(settings)
    fetcher = Fetcher(
        timeout_seconds=settings.request_timeout_seconds,
        max_attempts=2,
        backoff_seconds=0.25,
    )
    try:
        for app in selected_apps:
            artifact = retrieve_plan(
                plan_research(app),
                fetcher,
                search_provider,
                per_query_limit=args.per_query_limit,
                max_candidates=args.max_candidates,
            )
            save_retrieval_artifact(artifact)
            fetched = sum(source.status.value == "fetched" for source in artifact.fetched_sources)
            failed = len(artifact.fetched_sources) - fetched
            print(
                f"{app.name}: fetched={fetched}; failed={failed}; "
                f"sources={len(artifact.fetched_sources)}"
            )
    finally:
        fetcher.close()
        if search_provider is not None:
            search_provider.close()


if __name__ == "__main__":
    main()
