from __future__ import annotations

from typing import Dict, List, Literal, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - API layer is optional in this phase

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(default=None, **_kwargs):  # type: ignore[no-redef]
        return default


MAX_TEXT_LENGTH = 50_000
# Collection/element caps. Without them a single authenticated request could
# ship an unbounded list of unbounded strings.
MAX_ERROR_TYPES = 50
MAX_AMBIGUITIES = 200
MAX_AMBIGUITY_OPTIONS = 20
MAX_ALTERNATIVE_EXPANSIONS = 50
MAX_RESOLUTION_OVERRIDES = 500

try:
    from typing import Annotated

    ShortLabel = Annotated[str, Field(max_length=64)]
    ShortText = Annotated[str, Field(max_length=500)]
except ImportError:  # pragma: no cover - Python < 3.9
    ShortLabel = str  # type: ignore[misc,assignment]
    ShortText = str  # type: ignore[misc,assignment]


class NormalizeRequest(BaseModel):
    text: str = Field(
        ..., min_length=1, max_length=MAX_TEXT_LENGTH, description="Raw text to normalize"
    )
    domain: str = Field(default="general", max_length=64)


class NormalizeResponse(BaseModel):
    normalized_text: str
    error_types: List[str] = Field(default_factory=list)
    pending_submissions: List[dict] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class LiveNormalizeRequest(BaseModel):
    progressive: bool = False
    text: str = Field(..., max_length=MAX_TEXT_LENGTH, description="Raw text to normalize live")
    domain: str = Field(default="general", max_length=64)
    resolution_overrides: Dict[str, ShortText] = Field(
        default_factory=dict, alias="resolutionOverrides", max_length=MAX_RESOLUTION_OVERRIDES
    )
    input_method: Literal["typing", "paste"] = Field(default="paste", alias="inputMethod")
    allow_ai: bool = Field(default=False, alias="allowAI")


class VariantResolutionResponse(BaseModel):
    ambiguity_id: str = Field(alias="ambiguity_id")
    meaning: str


class LiveVariantResponse(BaseModel):
    id: str
    output: str
    resolutions: List[VariantResolutionResponse] = Field(default_factory=list)
    is_primary: bool = Field(alias="isPrimary")


class LiveAmbiguityResponse(BaseModel):
    id: str
    abbr: str
    token_index: int = Field(alias="token_index")
    options: List[str] = Field(default_factory=list)
    selected: str


class PhraseMatchResponse(BaseModel):
    start: int
    end: int
    matched: str
    expanded: str
    confidence: float = 1.0
    source: str = "override"


class ExpandedAbbreviationResponse(BaseModel):
    abbr: str
    expanded: str
    start: int
    end: int
    source: str = "token"
    candidate_id: str | None = Field(default=None, alias="candidateId")
    revision: int | None = None
    policy_version: str | None = Field(default=None, alias="policyVersion")


class NormalizationChangeResponse(BaseModel):
    id: str
    source: str | None = None
    candidate_id: str | None = Field(default=None, alias="candidateId")
    revision: int | None = None
    policy_version: str | None = Field(default=None, alias="policyVersion")
    reason: str | None = None
    confidence: float | None = None
    kinds: List[str] = Field(default_factory=list)
    original_start: int = Field(alias="originalStart")
    original_end: int = Field(alias="originalEnd")
    output_start: int = Field(alias="outputStart")
    output_end: int = Field(alias="outputEnd")
    original_text: str = Field(alias="originalText")
    output_text: str = Field(alias="outputText")


class LiveNormalizeResponse(BaseModel):
    primary_output: str = Field(alias="primaryOutput")
    variants: List[LiveVariantResponse] = Field(default_factory=list)
    ambiguities: List[LiveAmbiguityResponse] = Field(default_factory=list)
    pending_submissions: List[dict] = Field(default_factory=list, alias="pendingSubmissions")
    warnings: List[str] = Field(default_factory=list)
    error_types: List[str] = Field(default_factory=list, alias="errorTypes")
    latency_ms: float = Field(alias="latencyMs")
    phrase_matches: List[PhraseMatchResponse] = Field(default_factory=list, alias="phraseMatches")
    diacritic_applied: bool = Field(default=False, alias="diacriticApplied")
    diacritic_changes: List[List[str]] = Field(default_factory=list, alias="diacriticChanges")
    semantic_verified: bool = Field(default=False, alias="semanticVerified")
    semantic_corrections: List[List[str]] = Field(default_factory=list, alias="semanticCorrections")
    semantic_confidence: float = Field(default=0.0, alias="semanticConfidence")
    semantic_status: Literal[
        "not_needed",
        "not_checked",
        "verified",
        "uncertain",
        "partial",
        "unavailable",
        "quota",
        "error",
    ] = Field(default="not_needed", alias="semanticStatus")
    semantic_status_reason: Optional[str] = Field(default=None, alias="semanticStatusReason")
    semantic_verified_chunks: int = Field(default=0, alias="semanticVerifiedChunks")
    semantic_total_chunks: int = Field(default=0, alias="semanticTotalChunks")
    semantic_from_cache: bool = Field(default=False, alias="semanticFromCache")
    changes: List[NormalizationChangeResponse] = Field(default_factory=list)
    expanded_abbreviations: List[ExpandedAbbreviationResponse] = Field(
        default_factory=list,
        alias="expandedAbbreviations",
    )


class PendingApprovalRequest(BaseModel):
    expanded: Optional[str] = None
    review_notes: Optional[str] = None


class AddAbbreviationMeaningRequest(BaseModel):
    abbr: str = Field(..., min_length=1, max_length=100)
    meaning: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(default="general", max_length=100)
    approve_immediately: bool = Field(default=False)
    review_notes: Optional[str] = Field(default=None, max_length=1000)


class UserAbbreviationMeaningRequest(BaseModel):
    abbr: str = Field(..., min_length=1, max_length=100)
    meaning: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(default="general", max_length=100)


class AbbreviationUpsertRequest(BaseModel):
    expanded: str = Field(..., min_length=1, max_length=500)
    alternative_expansions: List[ShortText] = Field(
        default_factory=list, max_length=MAX_ALTERNATIVE_EXPANSIONS
    )
    domain: str = Field(default="general", max_length=100)


class PendingRejectionRequest(BaseModel):
    review_notes: Optional[str] = None


class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class AuthLogoutRequest(BaseModel):
    token: Optional[str] = Field(default=None, max_length=4096)


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    roles: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    expires_at: int = Field(alias="expiresAt")
    user: UserResponse


class DictionarySyncResponse(BaseModel):
    revision: int = Field(ge=0)
    status: Literal["not_exported", "synced", "export_failed"]
    database_committed: Optional[bool] = None


class AbbreviationResponse(BaseModel):
    dictionary_sync: Optional[DictionarySyncResponse] = None
    id: str
    abbr: str
    expanded: str
    alternative_expansions: List[str] = Field(default_factory=list)
    domain: str
    source: str
    created_at: Optional[str] = None
    approved_by: Optional[str] = None


class PendingAbbreviationResponse(BaseModel):
    id: str
    abbr: str
    suggested: Optional[str] = None
    suggested_meanings: List[str] = Field(default_factory=list)
    domain: str
    source: str
    status: str
    submission_count: int
    submitted_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    approved_abbreviation_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    has_suggested: bool = False


class DisambiguateAmbiguityItem(BaseModel):
    abbr: str = Field(..., min_length=1, max_length=100)
    options: List[ShortText] = Field(default_factory=list, max_length=MAX_AMBIGUITY_OPTIONS)


class DisambiguateRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
        description="Normalised text for context-aware refinement",
    )
    ambiguities: List[DisambiguateAmbiguityItem] = Field(
        default_factory=list,
        max_length=MAX_AMBIGUITIES,
        description="Ambiguous abbreviations with their options",
    )
    allow_ai: bool = Field(default=False, alias="allowAI")


class DisambiguationChoice(BaseModel):
    abbr: str
    chosen: str
    confidence: float
    reason: str
    is_new: bool = Field(default=False, alias="isNew")


class DisambiguateResponse(BaseModel):
    refined_text: str = Field(alias="refinedText")
    disambiguations: List[DisambiguationChoice] = Field(default_factory=list)
    confidence: float
    from_cache: bool = Field(default=False, alias="fromCache")


class DiacriticRestoreRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
        description="Text to restore diacritics for",
    )
    force: bool = Field(
        default=False, description="Force restoration even if text appears to have diacritics"
    )
    allow_ai: bool = Field(default=False, alias="allowAI")


class DiacriticRestoreResponse(BaseModel):
    restored_text: str = Field(alias="restoredText")
    confidence: float
    changed_tokens: list[list[str]] = Field(default_factory=list, alias="changedTokens")
    engine: str
    fallback_used: bool = Field(alias="fallbackUsed")
    latency_ms: int = Field(alias="latencyMs")


class AssignRoleRequest(BaseModel):
    role_name: str = Field(alias="roleName")


class HistoryCreateRequest(BaseModel):
    input_text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    output_text: Optional[str] = Field(default=None, max_length=MAX_TEXT_LENGTH)
    # Bounded: the column is NVARCHAR(500) and an unbounded list of unbounded
    # strings was a cheap memory-amplification vector on an authenticated POST.
    error_types: List[ShortLabel] = Field(default_factory=list, max_length=MAX_ERROR_TYPES)
    latency_ms: Optional[float] = None
    domain: str = Field(default="general", max_length=64)
    source_kind: str = Field(default="web_live", max_length=64)


class PreferenceSetRequest(BaseModel):
    value: str = Field(..., min_length=1, max_length=4000)
    category: str = Field(default="general", min_length=1, max_length=64)


class PhraseOverrideCreateRequest(BaseModel):
    phrase_key: str = Field(..., min_length=1, max_length=200)
    phrase_value: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(default="general", min_length=1, max_length=64)
    priority: int = Field(default=0, ge=0, le=1000)
    notes: Optional[str] = Field(default=None, max_length=1000)


class PhraseOverrideUpdateRequest(BaseModel):
    phrase_value: Optional[str] = Field(default=None, min_length=1, max_length=500)
    priority: Optional[int] = Field(default=None, ge=0, le=1000)
    notes: Optional[str] = Field(default=None, max_length=1000)


class HistoryEntryResponse(BaseModel):
    id: str
    input_text: str
    output_text: Optional[str] = None
    error_types: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    from_cache: bool = False
    latency_ms: Optional[float] = None
    domain: str
    source_kind: str
    user_id: Optional[str] = None
    username_snapshot: Optional[str] = None
    created_at: Optional[str] = None
