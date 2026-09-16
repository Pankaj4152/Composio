"""Read-only, conservative matching against the current Composio toolkit catalog."""

from dataclasses import dataclass
import re
from typing import Any, Protocol

from composio_research.config import Settings


class ToolkitCatalogClient(Protocol):
    class toolkits:  # type: ignore[valid-type]
        @staticmethod
        def list(**kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class ComposioCheckResult:
    app_name: str
    has_toolkit: bool | None
    matched_slug: str | None
    notes: str


def normalize_name(value: str) -> str:
    """Normalize product names without making fuzzy matches look certain."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _read(value: object, field: str) -> object | None:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def _items(response: object) -> list[object]:
    items = _read(response, "items")
    return items if isinstance(items, list) else []


def _next_cursor(response: object) -> str | None:
    cursor = _read(response, "next_cursor")
    return cursor if isinstance(cursor, str) and cursor else None


class ComposioCatalogChecker:
    """Catalog-only enrichment; it never creates a connection, auth config, or tool."""

    def __init__(self, settings: Settings, *, client: ToolkitCatalogClient | None = None) -> None:
        self._unavailable_reason: str | None = None
        if client is None:
            if settings.composio_api_key is None:
                self._unavailable_reason = "COMPOSIO_API_KEY is not configured; catalog match is unknown."
                self.client = None
                return
            try:
                from composio import Composio

                client = Composio(api_key=settings.composio_api_key)
            except Exception as error:
                self._unavailable_reason = f"Could not initialize the Composio SDK: {error}"
                self.client = None
                return
        self.client = client

    def check(self, app_name: str) -> ComposioCheckResult:
        if self.client is None:
            return ComposioCheckResult(app_name, None, None, self._unavailable_reason or "Catalog unavailable.")
        items: list[object] = []
        cursor: str | None = None
        # The current SDK exposes cursor pagination. Bound it defensively so a
        # malformed API response cannot make the research run loop forever.
        for _ in range(50):
            try:
                response = self.client.toolkits.list(limit=100, cursor=cursor)
            except Exception as error:
                message = re.sub(r"Invalid API key:\s*[^'\s,}]+", "Invalid API key: [redacted]", str(error))
                return ComposioCheckResult(app_name, None, None, f"Composio catalog query failed: {message}")
            items.extend(_items(response))
            cursor = _next_cursor(response)
            if cursor is None:
                break
        else:
            return ComposioCheckResult(app_name, None, None, "Catalog pagination exceeded the safe 50-page limit.")

        target = normalize_name(app_name)
        exact_matches: list[tuple[str, str]] = []
        near_matches: list[tuple[str, str]] = []
        for item in items:
            name = _read(item, "name")
            slug = _read(item, "slug")
            if not isinstance(name, str) or not isinstance(slug, str):
                continue
            normalized_name = normalize_name(name)
            normalized_slug = normalize_name(slug)
            if target in {normalized_name, normalized_slug}:
                exact_matches.append((name, slug))
            elif target and (target in normalized_name or target in normalized_slug):
                near_matches.append((name, slug))

        if len(exact_matches) == 1:
            name, slug = exact_matches[0]
            return ComposioCheckResult(app_name, True, slug, f"Exact Composio catalog match: {name} ({slug}).")
        if len(exact_matches) > 1:
            return ComposioCheckResult(app_name, None, None, "Multiple exact catalog matches; manual review required.")
        if near_matches:
            options = ", ".join(f"{name} ({slug})" for name, slug in near_matches[:3])
            return ComposioCheckResult(app_name, None, None, f"Possible catalog match(es), not asserted: {options}.")
        return ComposioCheckResult(app_name, False, None, "No exact match in the complete catalog response.")
