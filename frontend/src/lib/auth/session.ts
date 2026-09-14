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
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getSessionUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function setSession(
  token: string,
  user: SessionUser
): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

/** Dev-only role when no JWT is present. */
export function getDevRole(): UserRole | null {
  if (typeof window === "undefined") return null;
  return (window.localStorage.getItem(DEV_ROLE_KEY) as UserRole | null) ?? null;
}

export function setDevRole(role: UserRole): void {
  window.localStorage.setItem(DEV_ROLE_KEY, role);
}
