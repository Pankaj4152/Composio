"""Normalized, evidence-first data models for integration research."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthMethod(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    SESSION_OR_COOKIE = "session_or_cookie"
    SERVICE_ACCOUNT = "service_account"
    CLI_OR_LOCAL = "cli_or_local"
    NONE_PUBLIC = "none_public"
    OTHER = "other"
    UNKNOWN = "unknown"


class CredentialAccess(str, Enum):
    FREE_SELF_SERVE = "free_self_serve"
    TRIAL_SELF_SERVE = "trial_self_serve"
    PAID_SELF_SERVE = "paid_self_serve"
    ADMIN_APPROVAL = "admin_approval"
    APP_REVIEW = "app_review"
    ENTERPRISE_PLAN = "enterprise_plan"
    PARTNER_ONLY = "partner_only"
    CONTACT_SALES = "contact_sales"
    UNAVAILABLE = "unavailable"
    UNCLEAR = "unclear"


class ApiSurface(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    REST_AND_GRAPHQL = "rest_and_graphql"
    RPC_OR_OTHER = "rpc_or_other"
    CLI_ONLY = "cli_only"
    NONE_PUBLIC = "none_public"
    UNKNOWN = "unknown"


class ApiBreadth(str, Enum):
    NARROW = "narrow"
    MODERATE = "moderate"
    BROAD = "broad"
    UNKNOWN = "unknown"


class MCPStatus(str, Enum):
    OFFICIAL = "official"
    VENDOR_SUPPORTED = "vendor_supported"
    COMMUNITY = "community"
    NONE_FOUND = "none_found"
    UNKNOWN = "unknown"


class BuildabilityVerdict(str, Enum):
    BUILD_NOW = "build_now"
    BUILD_WITH_FRICTION = "build_with_friction"
    OUTREACH = "outreach"
    BLOCKED = "blocked"


class BlockerType(str, Enum):
    NONE = "none"
    NO_PUBLIC_API = "no_public_api"
    PAID_PLAN = "paid_plan"
    ENTERPRISE_ONLY = "enterprise_only"
    ADMIN_APPROVAL = "admin_approval"
    APP_REVIEW = "app_review"
    PARTNER_APPROVAL = "partner_approval"
    CONTACT_SALES = "contact_sales"
    LIMITED_API = "limited_api"
    LOCAL_ONLY = "local_only"
    UNSUPPORTED_AUTH = "unsupported_auth"
    UNCLEAR_DOCS = "unclear_docs"
    OTHER = "other"


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceSourceType(str, Enum):
    OFFICIAL_DOCS = "official_docs"
    OFFICIAL_HELP = "official_help"
    OFFICIAL_PRODUCT = "official_product"
    OFFICIAL_GITHUB = "official_github"
    SECONDARY = "secondary"


class EvidenceSupport(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    CONFLICTING = "conflicting"


class VerificationStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    UNVERIFIABLE = "unverifiable"


class AuditSampleType(str, Enum):
    REPRESENTATIVE = "representative"
    CHALLENGE = "challenge"


class StrictModel(BaseModel):
    """Base model that rejects unknown fields instead of silently dropping them."""

    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    """Evidence for one specific claim, rather than a generic URL collection."""

    field: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source_type: EvidenceSourceType
    support: EvidenceSupport
    excerpt: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class AppRecord(StrictModel):
    """A normalized agent research result for one app and one frozen pass."""

    id: int = Field(ge=1)
    app: str = Field(min_length=1)
    category: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    one_liner: str = Field(min_length=1)

    auth_methods: list[AuthMethod] = Field(min_length=1)
    credential_access: CredentialAccess
    additional_access_conditions: list[CredentialAccess] = Field(default_factory=list)
    access_notes: str | None = None

    api_surface: ApiSurface
    api_breadth: ApiBreadth

    mcp_status: MCPStatus
    mcp_source_url: str | None = None

    composio_has_toolkit: bool | None = None
    composio_toolkit_notes: str | None = None

    buildability_verdict: BuildabilityVerdict
    blocker_type: BlockerType
    blocker_detail: str | None = None

    evidence: list[Evidence] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    agent_notes: str = ""

    pass_number: int = Field(ge=1)
    manual_override: bool = False

    @property
    def confidence_label(self) -> ConfidenceLabel:
        """Derive a UI label from the canonical numeric confidence value."""
        if self.overall_confidence >= 0.9:
            return ConfidenceLabel.HIGH
        if self.overall_confidence >= 0.75:
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LOW


class ClaimVerification(StrictModel):
    """An independent verdict on whether one source supports one claim."""

    app_id: int = Field(ge=1)
    field: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    status: VerificationStatus
    explanation: str = Field(min_length=1)
    verifier_confidence: float = Field(ge=0.0, le=1.0)


class HumanAuditRecord(StrictModel):
    """A human ground-truth check that never overwrites the frozen prediction."""

    app_id: int = Field(ge=1)
    app: str = Field(min_length=1)
    pass_number: int = Field(ge=1)
    field: str = Field(min_length=1)
    frozen_agent_value: str
    human_ground_truth: str
    correct: bool
    official_evidence_url: str = Field(min_length=1)
    note: str = ""
    sample_type: AuditSampleType
