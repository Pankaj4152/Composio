"""Tests for generated JSON artifact persistence."""

from pathlib import Path

import pytest

from composio_research.schema import AuthMethod
from composio_research.serialization import read_json, write_json


def test_write_and_read_json_round_trip_with_enum(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "artifact.json"
    write_json(output_path, {"auth": AuthMethod.OAUTH2, "label": "नमस्ते"})

    assert read_json(output_path) == {"auth": "oauth2", "label": "नमस्ते"}
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_atomic_write_replaces_existing_complete_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "artifact.json"
    write_json(output_path, {"pass": 1, "complete": True})
    write_json(output_path, {"pass": 2, "complete": True})

    assert read_json(output_path) == {"complete": True, "pass": 2}
    assert list(tmp_path.glob(".*.tmp")) == []


def test_write_json_keeps_existing_file_when_data_is_not_serializable(tmp_path: Path) -> None:
    output_path = tmp_path / "artifact.json"
    write_json(output_path, {"status": "known-good"})

    with pytest.raises(TypeError, match="Cannot serialize"):
        write_json(output_path, {"bad": object()})

    assert read_json(output_path) == {"status": "known-good"}


def test_read_json_reports_malformed_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "artifact.json"
    output_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        read_json(output_path)
