import type {
  ApprovedAbbreviation,
  AIUsageStats,
  AuthResponse,
  AuthUser,
  DailyUsageStat,
  DiacriticRestoreResponse,
  LiveInputMethod,
  LiveNormalizeResponse,
  NormalizationHistoryEntry,
  PhraseOverride,
  PendingAbbreviation,
  UsageStat,
  UserMeaningResponse,
  UserPreference,
  UserSession,
} from "../types";

// In production the SPA is served from the same origin as the API, so an empty
// base keeps requests relative. A hardcoded localhost default used to get baked
// straight into the production bundle. `vite.config.ts` fails the build when
// VITE_API_BASE_URL is missing and a different origin is required.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.PROD ? "" : "http://localhost:8000");

/** Fired when the API rejects our token; AuthProvider listens and signs out. */
export const UNAUTHORIZED_EVENT = "viet-normalizer:unauthorized";

// Endpoints where a 401 is the expected answer to bad credentials rather than
// an expired session.
const AUTH_ENTRY_PATHS = ["/api/auth/login", "/api/auth/register"];

/** Keepalive requests are capped at 64 KB by the browser; stay under it. */
export const KEEPALIVE_MAX_BODY_BYTES = 60_000;

type RequestOptions = {
  onProgress?: (response: LiveNormalizeResponse) => void;
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
  keepalive?: boolean;
};

export class ApiError extends Error {
  status: number;
  databaseCommitted: boolean;

  constructor(message: string, status: number, databaseCommitted = false) {
    super(message);
    this.status = status;
    this.databaseCommitted = databaseCommitted;
  }
}

/** Turn any FastAPI error body into a string a human can read. */
function toErrorMessage(payload: unknown, status: number): string {
  const detail = (payload as { detail?: unknown } | null)?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  // 422 validation errors arrive as a list of objects; rendering them directly
  // produced "[object Object]" in the UI.
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        const msg = (item as { msg?: unknown })?.msg;
        const loc = (item as { loc?: unknown })?.loc;
        const field = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
        if (typeof msg === "string") return field ? `${field}: ${msg}` : msg;
        return "";
      })
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail === "object") {
    const msg = (detail as { msg?: unknown; message?: unknown }).msg ??
      (detail as { message?: unknown }).message;
    if (typeof msg === "string" && msg.trim()) return msg;
  }

  if (status === 401) return "Phien dang nhap da het han. Vui long dang nhap lai.";
  if (status === 403) return "Ban khong co quyen thuc hien thao tac nay.";
  if (status === 413) return "Noi dung gui len qua lon.";
  if (status === 429) return "Ban thao tac qua nhanh. Vui long thu lai sau it giay.";
  if (status >= 500) return "May chu dang gap su co. Vui long thu lai sau.";
  return "Co loi xay ra khi goi API.";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const body = options.body ? JSON.stringify(options.body) : undefined;

  // A keepalive request whose body exceeds the browser limit is dropped without
  // any error, so history written on tab close vanished silently. Send it as a
  // normal request instead — a chance to finish beats a guaranteed loss.
  let keepalive = options.keepalive ?? false;
  if (keepalive && body && new TextEncoder().encode(body).length > KEEPALIVE_MAX_BODY_BYTES) {
    keepalive = false;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body,
    signal: options.signal,
    keepalive,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    // 403 means "logged in but not allowed" — signing out there would eject a
    // normal user who merely opened an admin route.
    if (response.status === 401 && !AUTH_ENTRY_PATHS.includes(path)) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(toErrorMessage(payload, response.status), response.status,
      (payload as { database_committed?: boolean } | null)?.database_committed === true);
  }

  if (options.onProgress && response.headers.get("content-type")?.includes("application/x-ndjson")) {
    if (!response.body) throw new ApiError("Khong nhan duoc ket qua AI.", 502);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let final: LiveNormalizeResponse | undefined;
    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        if (buffer.length > 8_000_000) throw new ApiError("Ket qua AI qua lon.", 502);
        let newline: number;
        while ((newline = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, newline);
          buffer = buffer.slice(newline + 1);
          if (!line.trim()) continue;
          const event = JSON.parse(line) as { result: LiveNormalizeResponse; complete: boolean };
          if (!event.result || typeof event.result.primaryOutput !== "string") throw new ApiError("Ket qua AI khong hop le.", 502);
          if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
          if (event.complete) final = event.result;
          else options.onProgress(event.result);
        }
        if (done) break;
      }
      // Flush the decoder and handle a final event that arrived WITHOUT a
      // trailing newline (server cut, proxy, or future backend change). Before,
      // the tail was dropped and a fully delivered result surfaced as
      // "Ket noi AI bi gian doan" (502).
      buffer += decoder.decode();
      if (buffer.trim()) {
        try {
          const event = JSON.parse(buffer) as { result: LiveNormalizeResponse; complete: boolean };
          if (!event.result || typeof event.result.primaryOutput !== "string") throw new ApiError("Ket qua AI khong hop le.", 502);
          if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
          if (event.complete) final = event.result;
          else options.onProgress(event.result);
        } catch (error) {
          if (error instanceof ApiError || error instanceof DOMException) throw error;
          // Malformed tail: keep the pre-existing behavior — a completed
          // result stays usable, otherwise the "interrupted" error below
          // fires exactly as it did when the tail was silently ignored.
          if (!final) throw new ApiError("Ket noi AI bi gian doan.", 502);
        }
      }
      if (!final) throw new ApiError("Ket noi AI bi gian doan.", 502);
      return final as T;
    } finally {
      await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }
  return response.json() as Promise<T>;
}

export type AIMeaning = {
  id: string; abbr: string; meaning: string; domain: string; status: string;
  evidence_count: number; confidence: number; revision: number; policy_version: string;
  provider: string; model: string;
};
export type AIMeaningDetail = {
  candidate: AIMeaning;
  evidence: { context_snippet: string; created_at: string }[];
  audit: { id: string; action: string; actor: string; reason: string; revision: number; created_at: string }[];
};

export const api = {
  aiMeanings(token: string, filters: { status: string; domain: string; abbr: string; offset: number }) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) if (value !== "") params.set(key, String(value));
    return request<AIMeaning[]>(`/api/admin/ai-meanings?${params}`, { token });
  },
  aiMeaningDetail(token: string, id: string) {
    return request<AIMeaningDetail>(`/api/admin/ai-meanings/${id}`, { token });
  },
  moderateAIMeanings(token: string, ids: string[], action: "revoke" | "confirm", reason: string) {
    return request<{ items: AIMeaning[]; cacheStatus: string }>("/api/admin/ai-meanings/moderate", {
      token, method: "POST", body: { ids, action, reason },
    });
  },
  dictionaryRevision(token: string) {
    return request<{ revision: number }>("/api/dictionary/revision", { token });
  },
  dictionarySyncStatus(token: string) {
    return request<{ revision: number; status: string }>("/api/admin/dictionary/sync-status", { token });
  },
  retryDictionaryExport(token: string) {
    return request<{ revision: number; status: string }>("/api/admin/dictionary/retry-export", { token, method: "POST" });
  },
  register(username: string, email: string, password: string) {
    return request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: { username, email, password },
    });
  },
  login(identifier: string, password: string) {
    return request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: { identifier, password },
    });
  },
  logout(token: string | null) {
    return request<{ status: string }>("/api/auth/logout", {
      method: "POST",
      body: {},
      token,
    });
  },
  me(token: string) {
    return request<AuthUser>("/api/auth/me", { token });
  },
  normalizeLive(
    text: string,
    resolutionOverrides: Record<string, string>,
    inputMethod: LiveInputMethod,
    token: string,
    allowAi = false,
    signal?: AbortSignal,
    onProgress?: (response: LiveNormalizeResponse) => void,
  ) {
    return request<LiveNormalizeResponse>("/api/normalize/live", {
      method: "POST",
      token,
      signal,
      onProgress,
      body: {
        progressive: Boolean(onProgress),
        text,
        resolutionOverrides,
        inputMethod,
        allowAI: allowAi,
      },
    });
  },
  getPending(token: string) {
    return request<PendingAbbreviation[]>("/api/pending", { token });
  },
  listAbbreviations(token: string) {
    return request<ApprovedAbbreviation[]>("/api/abbreviations", { token });
  },
  getAbbreviation(abbr: string, token: string) {
    return request<ApprovedAbbreviation>(`/api/abbreviations/${encodeURIComponent(abbr)}`, { token });
  },
  saveAbbreviation(
    token: string,
    abbr: string,
    expanded: string,
    alternativeExpansions: string[],
    domain = "general",
  ) {
    return request<ApprovedAbbreviation>(`/api/abbreviations/${encodeURIComponent(abbr)}`, {
      method: "PUT",
      token,
      body: {
        expanded,
        alternative_expansions: alternativeExpansions,
        domain,
      },
    });
  },
  approvePending(
    pendingId: string,
    token: string,
    expanded?: string,
    reviewNotes?: string,
    ): Promise<{ dictionary_sync?: { status: string } }> {
      return request<{ dictionary_sync?: { status: string } }>(`/api/abbreviations/${pendingId}/approve`, {
      method: "POST",
      token,
      body: { expanded, review_notes: reviewNotes },
    });
  },
  rejectPending(pendingId: string, token: string, reviewNotes?: string): Promise<void> {
    return request<void>(`/api/abbreviations/${pendingId}/reject`, {
      method: "POST",
      token,
      body: { review_notes: reviewNotes },
    });
  },
  addMeaning(
    token: string,
    abbr: string,
    meaning: string,
    approveImmediately = true,
  ): Promise<UserMeaningResponse> {
    return request<UserMeaningResponse>("/api/abbreviations/add-meaning", {
      method: "POST",
      token,
      body: {
        abbr,
        meaning,
        approve_immediately: approveImmediately,
      },
    });
  },
  listUsers(token: string) {
    return request<AuthUser[]>("/api/users", { token });
  },
  listMyHistory(token: string, limit = 30) {
    return request<NormalizationHistoryEntry[]>(`/api/history?limit=${limit}`, { token });
  },
  deleteAbbreviation(abbr: string, token: string, domain = "general") {
    return request<{ deleted: boolean }>(`/api/abbreviations/${encodeURIComponent(abbr)}?domain=${encodeURIComponent(domain)}`, { method: "DELETE", token });
  },
  recordHistory(
    token: string,
    payload: {
      inputText: string;
      outputText?: string | null;
      errorTypes?: string[];
      latencyMs?: number | null;
      domain?: string;
      sourceKind?: string;
    },
    options: {
      keepalive?: boolean;
    } = {},
  ) {
    return request<NormalizationHistoryEntry>("/api/history", {
      method: "POST",
      token,
      keepalive: options.keepalive,
      body: {
        input_text: payload.inputText,
        output_text: payload.outputText ?? null,
        error_types: payload.errorTypes ?? [],
        latency_ms: payload.latencyMs,
        domain: payload.domain ?? "general",
        source_kind: payload.sourceKind ?? "web_live",
      },
    });
  },
  deleteHistory(token: string, historyId: string) {
    return request<NormalizationHistoryEntry>(`/api/history/${historyId}`, {
      method: "DELETE",
      token,
    });
  },
  deleteUser(token: string, userId: string) {
    return request<AuthUser>(`/api/users/${userId}`, {
      method: "DELETE",
      token,
    });
  },
  listSessions(token: string) {
    return request<UserSession[]>("/api/sessions", { token });
  },
  revokeAllSessions(token: string) {
    return request<{ revoked: number }>("/api/sessions/revoke-all", {
      method: "POST",
      token,
      body: {},
    });
  },
  listPreferences(token: string, category?: string) {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<UserPreference[]>(`/api/preferences${query}`, { token });
  },
  setPreference(token: string, key: string, value: string, category = "general") {
    return request<{ key: string; value: string; category: string }>(
      `/api/preferences/${encodeURIComponent(key)}`,
      {
        method: "PUT",
        token,
        body: { value, category },
      },
    );
  },
  deletePreference(token: string, key: string) {
    return request<{ deleted: string }>(`/api/preferences/${encodeURIComponent(key)}`, {
      method: "DELETE",
      token,
    });
  },
  listPhraseOverrides(token: string, domain?: string) {
    const query = domain ? `?domain=${encodeURIComponent(domain)}` : "";
    return request<PhraseOverride[]>(`/api/admin/phrase-overrides${query}`, { token });
  },
  createPhraseOverride(
    token: string,
    payload: {
      phraseKey: string;
      phraseValue: string;
      domain?: string;
      priority?: number;
      notes?: string | null;
    },
  ) {
    return request<PhraseOverride>("/api/admin/phrase-overrides", {
      method: "POST",
      token,
      body: {
        phrase_key: payload.phraseKey,
        phrase_value: payload.phraseValue,
        domain: payload.domain ?? "general",
        priority: payload.priority ?? 0,
        notes: payload.notes ?? null,
      },
    });
  },
  updatePhraseOverride(
    token: string,
    overrideId: string,
    payload: {
      phraseValue?: string;
      priority?: number;
      notes?: string | null;
    },
  ) {
    return request<{ updated: string }>(
      `/api/admin/phrase-overrides/${encodeURIComponent(overrideId)}`,
      {
        method: "PUT",
        token,
        body: {
          phrase_value: payload.phraseValue,
          priority: payload.priority,
          notes: payload.notes,
        },
      },
    );
  },
  deletePhraseOverride(token: string, overrideId: string) {
    return request<{ deleted: string }>(
      `/api/admin/phrase-overrides/${encodeURIComponent(overrideId)}`,
      {
        method: "DELETE",
        token,
      },
    );
  },
  getTopUsageStats(token: string, days = 30, limit = 50) {
    const params = new URLSearchParams({
      days: String(days),
      limit: String(limit),
    });
    return request<UsageStat[]>(`/api/admin/usage-stats/top?${params.toString()}`, { token });
  },
  getDailyUsageStats(token: string, days = 7) {
    return request<DailyUsageStat[]>(`/api/admin/usage-stats/daily?days=${days}`, { token });
  },
  getAIUsageStats(token: string) {
    return request<AIUsageStats>("/api/admin/ai-usage", { token });
  },
  restoreDiacritic(token: string, text: string, force = false, allowAi = false, signal?: AbortSignal) {
    return request<DiacriticRestoreResponse>("/api/normalize/restore-diacritic", {
      method: "POST",
      token,
      signal,
      body: { text, force, allowAI: allowAi },
    });
  },
  disambiguate(
    token: string,
    text: string,
    ambiguities: { abbr: string; options: string[] }[],
    signal?: AbortSignal,
    allowAi = false,
  ) {
    return request<{
      refinedText: string;
      disambiguations: { abbr: string; chosen: string; confidence: number; reason: string }[];
      confidence: number;
      fromCache: boolean;
    }>("/api/normalize/disambiguate", {
      method: "POST",
      token,
      signal,
      body: { text, ambiguities, allowAI: allowAi },
    });
  },
};
