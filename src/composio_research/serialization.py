"""Reliable UTF-8 JSON artifact loading and atomic persistence."""

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import tempfile
from typing import Any

from pydantic import BaseModel


def _json_default(value: object) -> Any:
    """Convert supported model values to JSON-compatible structures."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON.")


def write_json(path: Path, data: object) -> None:
    """Write JSON atomically so a failed/interrupted write preserves the old file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        data,
        default=_json_default,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def read_json(path: Path) -> Any:
    """Load one UTF-8 JSON artifact with a contextual error for malformed files."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error.msg}") from error
