"""Validation for the fixed assignment input list."""

from collections import Counter
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from composio_research.apps import APPS, CATEGORIES, DATASET_PATH, load_apps


def test_contains_exactly_100_apps() -> None:
    assert len(APPS) == 100
    assert DATASET_PATH.name == "apps.input.json"


def test_ids_are_unique_and_cover_the_assignment_range() -> None:
    assert [app.id for app in APPS] == list(range(1, 101))
    assert len({app.id for app in APPS}) == 100


def test_app_names_are_unique() -> None:
    names = [app.name for app in APPS]
    assert len(names) == len(set(names))


def test_categories_match_the_assignment_and_each_contain_ten_apps() -> None:
    counts = Counter(app.category for app in APPS)
    assert tuple(counts) == CATEGORIES
    assert counts == Counter({category: 10 for category in CATEGORIES})


def test_first_and_last_assignment_records_are_preserved() -> None:
    assert APPS[0].id == 1
    assert APPS[0].name == "Salesforce"
    assert APPS[0].category == "CRM and Sales"
    assert APPS[0].hint == "salesforce.com"

    assert APPS[-1].id == 100
    assert APPS[-1].name == "Grain"
    assert APPS[-1].category == "AI, Research and Media-native"
    assert APPS[-1].hint == "grain.com (meeting notes)"


def test_non_url_hints_are_preserved_as_source_text() -> None:
    paygent = next(app for app in APPS if app.id == 84)
    assert paygent.hint == "paygent (NMI-powered)"


def test_source_entries_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        APPS[0].name = "Changed"  # type: ignore[misc]


def test_loader_rejects_malformed_json(tmp_path: Path) -> None:
    dataset_path = tmp_path / "apps.input.json"
    dataset_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        load_apps(dataset_path)


def test_loader_rejects_duplicate_app_names(tmp_path: Path) -> None:
    records = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    records[1]["name"] = records[0]["name"]
    dataset_path = tmp_path / "apps.input.json"
    dataset_path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate app names"):
        load_apps(dataset_path)
