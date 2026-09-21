const WORKSPACE_DRAFT_PREFIX = "viet-normalizer-workspace-draft:";
const WORKSPACE_SIGNATURE_PREFIX = "viet-normalizer-workspace-signature:";

export const WORKSPACE_FLUSH_EVENT = "workspace:flush-history";

type WorkspaceDraft = {
  text: string;
  resolutionOverrides?: Record<string, string>;
};

function readSessionValue(key: string) {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSessionValue(key: string, value: string | null) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    if (value === null) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(key, value);
  } catch {
    // Ignore sessionStorage write failures so the workspace remains usable.
  }
}

function draftKey(userId: string) {
  return `${WORKSPACE_DRAFT_PREFIX}${userId}`;
}

function signatureKey(userId: string) {
  return `${WORKSPACE_SIGNATURE_PREFIX}${userId}`;
}

export function readWorkspaceDraft(userId: string): WorkspaceDraft | null {
  const raw = readSessionValue(draftKey(userId));
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as WorkspaceDraft;
    if (typeof parsed.text !== "string" || typeof parsed.resolutionOverrides !== "object" || !parsed.resolutionOverrides) {
      writeSessionValue(draftKey(userId), null);
      return null;
    }
    return parsed;
  } catch {
    writeSessionValue(draftKey(userId), null);
    return null;
  }
}

export function writeWorkspaceDraft(userId: string, draft: WorkspaceDraft) {
  writeSessionValue(draftKey(userId), JSON.stringify(draft));
}

export function clearWorkspaceDraft(userId: string) {
  writeSessionValue(draftKey(userId), null);
}

export function readWorkspaceLastSavedSignature(userId: string) {
  return readSessionValue(signatureKey(userId));
}

export function writeWorkspaceLastSavedSignature(userId: string, signature: string | null) {
  writeSessionValue(signatureKey(userId), signature);
}

export function clearAllWorkspaceSessionState() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const keysToRemove: string[] = [];
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const key = window.sessionStorage.key(index);
      if (!key) {
        continue;
      }
      if (key.startsWith(WORKSPACE_DRAFT_PREFIX) || key.startsWith(WORKSPACE_SIGNATURE_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => window.sessionStorage.removeItem(key));
  } catch {
    // Ignore sessionStorage cleanup failures during logout.
  }
}
