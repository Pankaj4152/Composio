"""Load and validate the external 100-app research input dataset."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AppEntry:
    """One app from the fixed research assignment."""

    id: int
    name: str
    category: str
    hint: str


CATEGORIES: tuple[str, ...] = (
    "CRM and Sales",
    "Support and Helpdesk",
    "Communications and Messaging",
    "Marketing, Ads, Email and Social",
    "Ecommerce",
    "Data, SEO and Scraping",
    "Developer, Infra and Data platforms",
    "Productivity and Project Management",
    "Finance and Fintech",
    "AI, Research and Media-native",
)


DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "apps.input.json"


def _require_nonempty_string(value: Any, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Record {index} must have a non-empty string '{field}'.")
    return value


def load_apps(path: Path = DATASET_PATH) -> tuple[AppEntry, ...]:
    """Load the editable JSON dataset and reject unsafe source-data changes."""
    try:
        raw_records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"App dataset does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"App dataset is not valid JSON: {error.msg}") from error

    if not isinstance(raw_records, list):
        raise ValueError("App dataset must be a JSON array.")

    apps: list[AppEntry] = []
    for index, record in enumerate(raw_records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} must be a JSON object.")
        app_id = record.get("id")
        if not isinstance(app_id, int) or isinstance(app_id, bool):
            raise ValueError(f"Record {index} must have an integer 'id'.")
        apps.append(
            AppEntry(
                id=app_id,
                name=_require_nonempty_string(record.get("name"), "name", index),
                category=_require_nonempty_string(record.get("category"), "category", index),
                hint=_require_nonempty_string(record.get("hint"), "hint", index),
            )
        )

    _validate_assignment_set(apps)
    return tuple(apps)


def _validate_assignment_set(apps: list[AppEntry]) -> None:
    if len(apps) != 100:
        raise ValueError(f"App dataset must contain exactly 100 records; found {len(apps)}.")

    ids = [app.id for app in apps]
    if ids != list(range(1, 101)):
        raise ValueError("App dataset IDs must be ordered and cover every value from 1 through 100.")

    names = [app.name for app in apps]
    if len(names) != len(set(names)):
        raise ValueError("App dataset contains duplicate app names.")

    categories = [app.category for app in apps]
    if set(categories) != set(CATEGORIES):
        raise ValueError("App dataset categories do not match the assignment categories.")
    if any(categories.count(category) != 10 for category in CATEGORIES):
        raise ValueError("Each assignment category must contain exactly 10 apps.")


APPS = load_apps()
