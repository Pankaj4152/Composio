"""Small, replaceable web-search adapters for official-first retrieval."""

from typing import Any

import httpx

from composio_research.config import Settings
from composio_research.retrieval import SearchProvider, SearchResult


class SearchConfigurationError(ValueError):
    """Raised before a network call when search settings are incomplete."""


class SearchRequestError(RuntimeError):
    """Raised when a configured search provider does not return usable results."""


class _HttpSearchProvider(SearchProvider):
    """Shared HTTP lifecycle and response validation for provider adapters."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise SearchConfigurationError("SEARCH_API_KEY must not be empty.")
        self.api_key = api_key
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    @staticmethod
    def _parse_results(items: object, *, title_key: str, url_key: str, snippet_key: str) -> list[SearchResult]:
        if not isinstance(items, list):
            raise SearchRequestError("Search provider response did not contain a result list.")

        results: list[SearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get(url_key)
            if not isinstance(url, str) or not url.strip():
                continue
            title = item.get(title_key)
            snippet = item.get(snippet_key)
            results.append(
                SearchResult(
                    title=title if isinstance(title, str) else url,
                    url=url,
                    snippet=snippet if isinstance(snippet, str) else "",
                )
            )
        return results


class TavilySearchProvider(_HttpSearchProvider):
    """Adapter for Tavily's documented search endpoint."""

    endpoint = "https://api.tavily.com/search"

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        try:
            response = self.client.post(
                self.endpoint,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SearchRequestError(f"Tavily search failed: {error}") from error
        return self._parse_results(payload.get("results"), title_key="title", url_key="url", snippet_key="content")


class SerperSearchProvider(_HttpSearchProvider):
    """Adapter for Serper's Google web-search endpoint."""

    endpoint = "https://google.serper.dev/search"

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        try:
            response = self.client.post(
                self.endpoint,
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"q": query, "num": limit},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SearchRequestError(f"Serper search failed: {error}") from error
        return self._parse_results(payload.get("organic"), title_key="title", url_key="link", snippet_key="snippet")


def create_search_provider(settings: Settings, *, client: httpx.Client | None = None) -> SearchProvider:
    """Instantiate the configured provider or give an actionable configuration error."""
    if settings.search_provider is None:
        raise SearchConfigurationError(
            "SEARCH_PROVIDER is required for web search. Set it to 'tavily' or 'serper'."
        )
    if settings.search_api_key is None:
        raise SearchConfigurationError("SEARCH_API_KEY is required for web search.")

    provider = settings.search_provider.lower()
    common_arguments = {
        "api_key": settings.search_api_key,
        "timeout_seconds": settings.request_timeout_seconds,
        "client": client,
    }
    if provider == "tavily":
        return TavilySearchProvider(**common_arguments)
    if provider == "serper":
        return SerperSearchProvider(**common_arguments)
    raise SearchConfigurationError(
        f"Unsupported SEARCH_PROVIDER={settings.search_provider!r}. Use 'tavily' or 'serper'."
    )
