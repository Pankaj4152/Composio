"""Read-only Composio catalog check for one or all assignment apps."""

import argparse

from composio_research.apps import APPS
from composio_research.composio_check import ComposioCatalogChecker
from composio_research.config import LOG_DIR, load_settings
from composio_research.serialization import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", type=int)
    args = parser.parse_args()
    apps = [app for app in APPS if args.app_id is None or app.id == args.app_id]
    if args.app_id is not None and not apps:
        raise SystemExit(f"Unknown app id: {args.app_id}")
    checker = ComposioCatalogChecker(load_settings())
    results = tuple(checker.check(app.name) for app in apps)
    write_json(LOG_DIR / "composio" / "catalog_checks.json", results)
    print({"checked": len(results), "output": str(LOG_DIR / "composio" / "catalog_checks.json")})


if __name__ == "__main__":
    main()
