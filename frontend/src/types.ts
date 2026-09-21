export type AuthUser = {
  id: string;
  username: string;
  email: string;
  roles: string[];
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AuthResponse = {
  accessToken: string;
  expiresAt: number;
  user: AuthUser;
};

export type PendingSubmission = {
  abbr: string;
  status: string;
  pending_id?: string;
  has_suggested?: boolean;
  needs_user_meaning?: boolean;
  can_add_more_meanings?: boolean;
};

export type UserMeaningResponse = {
  status: string;
  abbr: string;
  meaning: string;
  pending_id?: string | null;
  review_required?: boolean;
  globally_approved?: boolean;
};

export type VariantResolution = {
  ambiguity_id: string;
  meaning: string;
};

export type LiveInputMethod = "typing" | "paste";

export type LiveVariant = {
  id: string;
  output: string;
  resolutions: VariantResolution[];
  isPrimary: boolean;
};

export type LiveAmbiguity = {
  id: string;
  abbr: string;
  token_index: number;
  options: string[];
  selected: string;
};

export type PhraseMatch = {
  start: number;
  end: number;
  matched: string;
  expanded: string;
  confidence: number;
  source: string;
};

export type ExpandedAbbreviation = {
  abbr: string;
  candidateId?: string | null;
  revision?: number | null;
  policyVersion?: string | null;
  expanded: string;
  start?: number;
  end?: number;
  source?: string;
  originalStart?: number;
  originalEnd?: number;
  original?: string;
};

export type NormalizationChange = {
  id: string;
  source?: string | null;
  candidateId?: string | null;
  revision?: number | null;
  policyVersion?: string | null;
  reason?: string | null;
  confidence?: number | null;
  kinds: string[];
  originalStart: number;
  originalEnd: number;
  outputStart: number;
  outputEnd: number;
  originalText: string;
  outputText: string;
};

export type LiveNormalizeResponse = {
  inputText?: string;
  inputVersion?: number;
  normalizationPhase?: "ai_pending" | "complete";
  primaryOutput: string;
  variants: LiveVariant[];
  ambiguities: LiveAmbiguity[];
  pendingSubmissions: PendingSubmission[];
  warnings: string[];
  errorTypes: string[];
  latencyMs: number;
  phraseMatches?: PhraseMatch[];
  diacriticApplied?: boolean;
  diacriticChanges?: [string, string][];
  semanticVerified?: boolean;
  semanticCorrections?: [string, string][];
  semanticConfidence?: number;
  semanticStatus?:
    | "not_needed"
    | "not_checked"
    | "verified"
    | "uncertain"
    | "partial"
    | "unavailable"
    | "quota"
    | "error";
  semanticStatusReason?: string | null;
  semanticVerifiedChunks?: number;
  semanticTotalChunks?: number;
  semanticFromCache?: boolean;
  changes?: NormalizationChange[];
  expandedAbbreviations?: ExpandedAbbreviation[];
};

export type ApprovedAbbreviation = {
  dictionary_sync?: { revision: number; status: string; database_committed?: boolean } | null;
  id: string;
  abbr: string;
  expanded: string;
  alternative_expansions: string[];
  domain: string;
  source: string;
  created_at?: string | null;
  approved_by?: string | null;
};

export type PendingAbbreviation = {
  id: string;
  abbr: string;
  suggested?: string | null;
  suggested_meanings: string[];
  domain: string;
  source: string;
  status: string;
  submission_count: number;
  submitted_by?: string | null;
  reviewed_by?: string | null;
  review_notes?: string | null;
  approved_abbreviation_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  has_suggested: boolean;
};

export type DiacriticRestoreResponse = {
  restoredText: string;
  confidence: number;
  changedTokens: [string, string][];
  engine: "rule" | "ai" | "hybrid" | "skip";
  fallbackUsed: boolean;
  latencyMs: number;
};

export type NormalizationHistoryEntry = {
  id: string;
  input_text: string;
  output_text?: string | null;
  error_types: string[];
  model_used?: string | null;
  from_cache: boolean;
  latency_ms?: number | null;
  domain: string;
  source_kind: string;
  user_id?: string | null;
  username_snapshot?: string | null;
  created_at?: string | null;
};

export type UserSession = {
  id: string;
  ip_address?: string | null;
  user_agent?: string | null;
  issued_at?: string | null;
  expires_at?: string | null;
  last_activity_at?: string | null;
};

export type UserPreference = {
  preference_key: string;
  preference_value: string;
  category: string;
  updated_at?: string | null;
};

export type PhraseOverride = {
  id: string;
  phrase_key: string;
  phrase_value: string;
  domain: string;
  source?: string | null;
  priority: number;
  notes?: string | null;
  created_by?: string | null;
  updated_at?: string | null;
};

export type UsageStat = {
  abbr: string;
  expanded_chosen: string;
  total_count: number;
  last_used?: string | null;
  active_days: number;
};

export type DailyUsageStat = {
  usage_date: string;
  unique_abbreviations: number;
  total_uses: number;
};

export type AIUsageStats = {
  call_count: number;
  tokens_used: number;
  rate_limited_count: number;
  error_count: number;
};
