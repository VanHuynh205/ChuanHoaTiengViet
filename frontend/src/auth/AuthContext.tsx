import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, ApiError, UNAUTHORIZED_EVENT } from "../lib/api";
import { clearResponseCache } from "../hooks/useLiveNormalize";
import { clearAllWorkspaceSessionState } from "../lib/workspaceSession";
import type { AuthResponse, AuthUser } from "../types";

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  isBootstrapping: boolean;
  isAuthenticated: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const SESSION_STORAGE_KEY = "viet-normalizer-session";
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type StoredSession = { token: string; user: AuthUser };

function isValidStoredSession(value: unknown): value is StoredSession {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.token === "string" &&
    candidate.token.length > 0 &&
    typeof candidate.user === "object" &&
    candidate.user !== null
  );
}

function readSession(): StoredSession | null {
  const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isValidStoredSession(parsed)) {
      return parsed;
    }
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  } catch {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

function writeSession(payload: AuthResponse) {
  sessionStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      token: payload.accessToken,
      user: payload.user,
    }),
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [, setBootstrapError] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    clearAllWorkspaceSessionState();
    // The live-normalize cache lives at module scope, so it would otherwise
    // survive the sign-out and leak one user's output to the next.
    clearResponseCache();
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const session = readSession();
    if (!session) {
      setIsBootstrapping(false);
      return;
    }

    api
      .me(session.token)
      .then((currentUser) => {
        setToken(session.token);
        setUser(currentUser);
      })
      .catch((caughtError: unknown) => {
        // Only a real rejection invalidates the session. A network blip or a
        // 5xx used to discard a perfectly valid token and force a re-login.
        const status = caughtError instanceof ApiError ? caughtError.status : 0;
        if (status === 401 || status === 403) {
          sessionStorage.removeItem(SESSION_STORAGE_KEY);
          return;
        }
        setBootstrapError("Khong ket noi duoc may chu. Vui long thu lai.");
      })
      .finally(() => {
        setIsBootstrapping(false);
      });
  }, []);

  // A token revoked or expired server-side surfaces as a 401 on any call; sign
  // out instead of leaving a dead token in sessionStorage forever.
  useEffect(() => {
    const handleUnauthorized = () => clearSession();
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [clearSession]);

  const handleAuthSuccess = (response: AuthResponse) => {
    writeSession(response);
    setToken(response.accessToken);
    setUser(response.user);
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isBootstrapping,
      isAuthenticated: Boolean(token && user),
      async login(identifier, password) {
        const response = await api.login(identifier, password);
        handleAuthSuccess(response);
      },
      async register(username, email, password) {
        const response = await api.register(username, email, password);
        handleAuthSuccess(response);
      },
      async logout() {
        try {
          await api.logout(token);
        } catch (caughtError) {
          if (!(caughtError instanceof ApiError)) {
            throw caughtError;
          }
        } finally {
          clearSession();
        }
      },
    }),
    [clearSession, isBootstrapping, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth phai duoc dung ben trong AuthProvider.");
  }
  return context;
}
