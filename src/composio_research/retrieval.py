"""Official-first retrieval, clean text extraction, and source artifact logging."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import time
from typing import Protocol
from urllib.parse import urlsplit
import re

import httpx
from lxml import etree, html as lxml_html

from composio_research.config import LOG_DIR
from composio_research.serialization import write_json
from composio_research.source_planner import (
    CandidateSourceType,
    HintSeed,
    PlannedQuery,
    ResearchPlan,
    RetrievalStatus,
    SourceCandidate,
    is_official_url,
)


class SearchProvider(Protocol):
    """Provider boundary; a future adapter supplies real web-search results."""

    def search(self, query: str, limit: int = 5) -> list["SearchResult"]: ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True, slots=True)
class FetchedSource:
    """The persisted, model-ready result of fetching one candidate source."""

    requested_url: str
    final_url: str | None
    source_type: CandidateSourceType
    is_official_domain: bool
    priority: int
    relevance_score: float
    requires_human_review: bool
    status: RetrievalStatus
    status_code: int | None
    title: str | None
    extracted_text: str | None
    fetched_at: str
    attempts: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalArtifact:
    """Traceable source collection record for one app."""

    app_id: int
    app_name: str
    plan: ResearchPlan
    fetched_sources: tuple[FetchedSource, ...]
    created_at: str


class Fetcher:
    """Small HTTP client with bounded retry behavior and clean-text extraction."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        client: httpx.Client | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": "ComposioResearchAgent/0.1 (+https://github.com/)"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self, candidate: SourceCandidate) -> FetchedSource:
        """Fetch one source without letting an individual failure stop a run."""
        last_error: str | None = None
        last_status_code: int | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.get(candidate.url)
                last_status_code = response.status_code
                response.raise_for_status()
                text, title = extract_main_text(response.text)
                return FetchedSource(
                    requested_url=candidate.url,
                    final_url=str(response.url),
                    source_type=candidate.source_type,
                    is_official_domain=candidate.is_official_domain,
                    priority=candidate.priority,
                    relevance_score=candidate.relevance_score,
                    requires_human_review=candidate.requires_human_review,
                    status=RetrievalStatus.FETCHED,
                    status_code=response.status_code,
                    title=title,
                    extracted_text=text,
                    fetched_at=utc_now(),
                    attempts=attempt,
                )
            except httpx.HTTPError as error:
                last_error = str(error)
                if attempt < self.max_attempts:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        return FetchedSource(
            requested_url=candidate.url,
            final_url=None,
            source_type=candidate.source_type,
            is_official_domain=candidate.is_official_domain,
            priority=candidate.priority,
            relevance_score=candidate.relevance_score,
            requires_human_review=candidate.requires_human_review,
            status=RetrievalStatus.FAILED,
            status_code=last_status_code,
            title=None,
            extracted_text=None,
            fetched_at=utc_now(),
            attempts=self.max_attempts,
            error=last_error or "Fetch failed without a captured HTTP error.",
        )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def extract_main_text(html: str) -> tuple[str, str | None]:
    """Extract readable main text and title; never pass raw HTML downstream."""
    try:
        document = lxml_html.fromstring(html)
    except (etree.ParserError, ValueError):
        return "", None

    titles = document.xpath("//title/text()")
    title = " ".join(titles[0].split()) if titles else None

    for node in document.xpath(
        "//script | //style | //noscript | //template | //svg | //iframe | "
        "//nav | //header | //footer | //aside | //form"
    ):
        node.drop_tree()

    main_candidates = document.xpath("//main | //article | //*[@role='main']")
    content_root = main_candidates[0] if main_candidates else document.find(".//body")
    if content_root is None:
        content_root = document

    text = " ".join(content_root.text_content().split())
    return text, title


def app_relevance_score(app_name: str, result: SearchResult) -> float:
    """Score whether a search result is about the requested app, not just its vendor."""
    normalized_app = _normalize_for_matching(app_name)
    app_terms = [term for term in normalized_app.split() if len(term) > 1]
    if not app_terms:
        return 0.0

    # Search snippets can echo the user's query even when the linked page is
    # about a different product. Treat title/URL as primary relevance signals.
    normalized_primary = _normalize_for_matching(f"{result.title} {result.url}")
    normalized_snippet = _normalize_for_matching(result.snippet)
    if normalized_app in normalized_primary:
        return 1.0

    primary_terms = normalized_primary.split()
    snippet_terms = normalized_snippet.split()
    primary_coverage = sum(term in primary_terms for term in app_terms) / len(app_terms)
    snippet_coverage = sum(term in snippet_terms for term in app_terms) / len(app_terms)
    return max(primary_coverage, snippet_coverage * 0.6)


def _normalize_for_matching(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def classify_search_result(
    result: SearchResult,
    official_domain: str | None,
    app_name: str,
) -> SourceCandidate:
    """Rank discovered URLs without overstating unverifiable GitHub ownership."""
    official = is_official_url(result.url, official_domain)
    host = urlsplit(result.url).hostname or ""
    host = host.lower()

    if official and any(token in host for token in ("docs.", "developer", "api.")):
        source_type, base_priority = CandidateSourceType.OFFICIAL_DOCS, 90
    elif official and any(token in host for token in ("help.", "support.")):
        source_type, base_priority = CandidateSourceType.OFFICIAL_HELP, 85
    elif official:
        source_type, base_priority = CandidateSourceType.OFFICIAL_PRODUCT, 80
    else:
        source_type, base_priority = CandidateSourceType.SECONDARY, 40

    relevance_score = app_relevance_score(app_name, result)
    requires_human_review = relevance_score < 0.75
    priority = round(base_priority * (0.5 + (0.5 * relevance_score)))

    return SourceCandidate(
        url=result.url,
        source_type=source_type,
        official_domain=official_domain,
        is_official_domain=official,
        priority=priority,
        selection_reason=f"Search result: {result.title}",
        title=result.title,
        snippet=result.snippet,
        relevance_score=relevance_score,
        requires_human_review=requires_human_review,
    )


def discover_candidates(
    plan: ResearchPlan,
    search_provider: SearchProvider | None = None,
    *,
    per_query_limit: int = 5,
) -> tuple[SourceCandidate, ...]:
    """Combine direct official hints with ranked search results, deduplicated by URL."""
    candidates: dict[str, SourceCandidate] = {candidate.url: candidate for candidate in plan.direct_candidates}

    if search_provider is not None:
        for query in plan.queries:
            for result in search_provider.search(query.query, limit=per_query_limit):
                candidate = classify_search_result(result, plan.hint.official_domain, plan.app_name)
                existing = candidates.get(candidate.url)
                if existing is None or candidate.priority > existing.priority:
                    candidates[candidate.url] = candidate

    return tuple(sorted(candidates.values(), key=lambda candidate: (-candidate.priority, candidate.url)))


def retrieve_plan(
    plan: ResearchPlan,
    fetcher: Fetcher,
    search_provider: SearchProvider | None = None,
    *,
    per_query_limit: int = 5,
    max_candidates: int = 6,
) -> RetrievalArtifact:
    """Collect and retain clean source text for one app; errors stay per-source."""
    candidates = discover_candidates(plan, search_provider, per_query_limit=per_query_limit)
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1.")
    candidates = candidates[:max_candidates]
    fetched_sources: list[FetchedSource] = []
    seen_canonical_urls: set[str] = set()
    for candidate in candidates:
        if canonicalize_url(candidate.url) in seen_canonical_urls:
            continue
        source = fetcher.fetch(candidate)
        canonical_url = canonicalize_url(source.final_url or source.requested_url)
        if canonical_url in seen_canonical_urls:
            continue
        seen_canonical_urls.add(canonical_url)
        fetched_sources.append(source)
    return RetrievalArtifact(
        app_id=plan.app_id,
        app_name=plan.app_name,
        plan=plan,
        fetched_sources=tuple(fetched_sources),
        created_at=utc_now(),
    )


def canonicalize_url(url: str) -> str:
    """Normalize URLs enough to remove duplicate source pages after redirects."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}"


def retrieval_artifact_path(app_id: int, log_dir: Path = LOG_DIR) -> Path:
    """Return the deterministic per-app retrieval artifact location."""
    return log_dir / "retrieval" / f"{app_id:03d}.json"


def save_retrieval_artifact(artifact: RetrievalArtifact, log_dir: Path = LOG_DIR) -> Path:
    """Persist a retrieval artifact with atomic JSON writes."""
    path = retrieval_artifact_path(artifact.app_id, log_dir)
    write_json(path, artifact)
    return path


def retrieval_artifact_from_dict(data: dict[str, object]) -> RetrievalArtifact:
    """Rehydrate a saved JSON retrieval artifact into typed nested objects."""
    raw_plan = data["plan"]
    if not isinstance(raw_plan, dict):
        raise ValueError("Retrieval artifact plan must be an object.")
    raw_hint = raw_plan["hint"]
    if not isinstance(raw_hint, dict):
        raise ValueError("Retrieval artifact hint must be an object.")
    raw_candidates = raw_plan["direct_candidates"]
    raw_queries = raw_plan["queries"]
    raw_sources = data["fetched_sources"]
    if not all(isinstance(value, list) for value in (raw_candidates, raw_queries, raw_sources)):
        raise ValueError("Retrieval artifact candidate, query, and source fields must be arrays.")

    plan = ResearchPlan(
        app_id=int(raw_plan["app_id"]),
        app_name=str(raw_plan["app_name"]),
        category=str(raw_plan["category"]),
        hint=HintSeed(**raw_hint),
        direct_candidates=tuple(
            SourceCandidate(
                **{
                    **candidate,
                    "source_type": CandidateSourceType(candidate["source_type"]),
                    "status": RetrievalStatus(candidate["status"]),
                    "relevance_score": candidate.get("relevance_score", 1.0),
                    "requires_human_review": candidate.get("requires_human_review", False),
                }
            )
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ),
        queries=tuple(PlannedQuery(**query) for query in raw_queries if isinstance(query, dict)),
    )
    sources = tuple(
        FetchedSource(
            **{
                **source,
                "source_type": CandidateSourceType(source["source_type"]),
                "status": RetrievalStatus(source["status"]),
                "relevance_score": source.get("relevance_score", 1.0),
                "requires_human_review": source.get("requires_human_review", False),
            }
        )
        for source in raw_sources
        if isinstance(source, dict)
    )
    return RetrievalArtifact(
        app_id=int(data["app_id"]),
        app_name=str(data["app_name"]),
        plan=plan,
        fetched_sources=sources,
        created_at=str(data["created_at"]),
    )
