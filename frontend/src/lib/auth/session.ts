/**
 * Browser session for JWT auth. Token lives in localStorage.
 * Dev role-header bypass is separate and only used when no token is set
 * and the UI explicitly keeps a role selector (AUTH_DEV_HEADER_BYPASS).
 */

import type { UserRole } from "@/lib/api/types";

const TOKEN_KEY = "qaegis.access_token";
const USER_KEY = "qaegis.user";
const DEV_ROLE_KEY = "qaegis.dev_role";

export type SessionUser = {
  id: string;
  email: string;
  role: UserRole;
  name: string;
};

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    // localStorage can throw (private mode, blocked cookies, quota).
    return null;
  }
}

export function getSessionUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: SessionUser): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // Non-fatal: auth still works for this tab via in-memory context state.
  }
}

export function clearSession(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
  } catch {
    // Nothing to clear if storage is unavailable.
  }
}

/** Dev-only role when no JWT is present. */
export function getDevRole(): UserRole | null {
  if (typeof window === "undefined") return null;
  try {
    return (
      (window.localStorage.getItem(DEV_ROLE_KEY) as UserRole | null) ?? null
    );
  } catch {
    return null;
  }
}

export function setDevRole(role: UserRole): void {
  try {
    window.localStorage.setItem(DEV_ROLE_KEY, role);
  } catch {
    // Non-fatal: the role still applies in-memory for this session.
  }
}
