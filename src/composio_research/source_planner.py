"""Plan official-first research sources before making any network requests."""

from dataclasses import dataclass
from enum import Enum
import re
from urllib.parse import urlsplit

from composio_research.apps import AppEntry


class CandidateSourceType(str, Enum):
    OFFICIAL_HINT = "official_hint"
    OFFICIAL_DOCS = "official_docs"
    OFFICIAL_HELP = "official_help"
    OFFICIAL_PRODUCT = "official_product"
    OFFICIAL_GITHUB = "official_github"
    SECONDARY = "secondary"


class RetrievalStatus(str, Enum):
    PLANNED = "planned"
    FETCHED = "fetched"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class HintSeed:
    """A parsed assignment hint, which may or may not contain a usable URL."""

    raw_hint: str
    direct_url: str | None
    official_domain: str | None


@dataclass(frozen=True, slots=True)
class PlannedQuery:
    """One focused discovery query and the evidence question it targets."""

    query: str
    purpose: str


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """A potential source to retrieve, retaining why it was selected."""

    url: str
    source_type: CandidateSourceType
    official_domain: str | None
    is_official_domain: bool
    priority: int
    selection_reason: str
    status: RetrievalStatus = RetrievalStatus.PLANNED


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    """All direct-source and discovery work planned for one app."""

    app_id: int
    app_name: str
    category: str
    hint: HintSeed
    direct_candidates: tuple[SourceCandidate, ...]
    queries: tuple[PlannedQuery, ...]


_PARENTHETICAL_NOTE = re.compile(r"\s*\([^)]*\)\s*$")
_HOST_HINT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]+)+(?:/[^\s]*)?$", re.IGNORECASE)


def parse_hint(raw_hint: str) -> HintSeed:
    """Convert a domain/path hint into HTTPS, but preserve non-web hints as text."""
    stripped_hint = _PARENTHETICAL_NOTE.sub("", raw_hint).strip()
    if not _HOST_HINT.fullmatch(stripped_hint):
        return HintSeed(raw_hint=raw_hint, direct_url=None, official_domain=None)

    direct_url = f"https://{stripped_hint}"
    hostname = urlsplit(direct_url).hostname
    if hostname is None:
        return HintSeed(raw_hint=raw_hint, direct_url=None, official_domain=None)
    return HintSeed(raw_hint=raw_hint, direct_url=direct_url, official_domain=hostname.lower())


def is_official_url(url: str, official_domain: str | None) -> bool:
    """Check domain ownership without accepting lookalike domains."""
    if official_domain is None:
        return False
    hostname = urlsplit(url).hostname
    if hostname is None:
        return False
    hostname = hostname.lower()
    official_domain = official_domain.lower()
    return hostname == official_domain or hostname.endswith(f".{official_domain}")


def plan_research(entry: AppEntry) -> ResearchPlan:
    """Create deterministic official-first sources and claim-focused queries."""
    hint = parse_hint(entry.hint)
    direct_candidates: tuple[SourceCandidate, ...] = ()
    domain_filter = ""

    if hint.direct_url and hint.official_domain:
        direct_candidates = (
            SourceCandidate(
                url=hint.direct_url,
                source_type=CandidateSourceType.OFFICIAL_HINT,
                official_domain=hint.official_domain,
                is_official_domain=True,
                priority=100,
                selection_reason="Supplied assignment hint; fetch before search results.",
            ),
        )
        domain_filter = f"site:{hint.official_domain} "

    app_name = f'"{entry.name}"'
    queries = (
        PlannedQuery(
            query=f"{domain_filter}{app_name} API documentation developer",
            purpose="Find official API and developer documentation.",
        ),
        PlannedQuery(
            query=f"{domain_filter}{app_name} API authentication OAuth API key credentials",
            purpose="Determine supported authentication and how credentials are obtained.",
        ),
        PlannedQuery(
            query=f"{domain_filter}{app_name} API access pricing enterprise partner app review",
            purpose="Determine API credential gates and commercial or approval requirements.",
        ),
        PlannedQuery(
            query=f"{domain_filter}{app_name} MCP server",
            purpose="Find actual official, vendor-supported, or community MCP implementations.",
        ),
    )

    return ResearchPlan(
        app_id=entry.id,
        app_name=entry.name,
        category=entry.category,
        hint=hint,
        direct_candidates=direct_candidates,
        queries=queries,
    )
