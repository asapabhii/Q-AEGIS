"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { UserRole } from "@/lib/api/types";
import {
  clearSession,
  getDevRole,
  getSessionUser,
  setDevRole,
  type SessionUser,
} from "@/lib/auth/session";
import { DEFAULT_ROLE } from "@/lib/auth/roles";

/**
 * Single source of the caller's identity for the whole app.
 *
 * Resolution order, established once on mount:
 *   1. A JWT session (getSessionUser) — the authenticated role is authoritative
 *      and the dev role selector is hidden.
 *   2. A stored dev role (getDevRole) — the X-Q-AEGIS-Actor-Role bypass.
 *   3. {@link DEFAULT_ROLE} — a sensible operator default for a fresh dev run.
 *
 * `setRole` also persists via `setDevRole` so the API client's header fallback
 * (client.ts authHeaders) and this context never disagree.
 */
interface RoleContextType {
  /** Effective caller role (JWT role when authenticated, else the dev role). */
  role: UserRole;
  /** Change the dev role. No-op on the server as far as the header goes when a JWT is present (Bearer wins). */
  setRole: (role: UserRole) => void;
  /** The authenticated user, or null when running on the dev header bypass. */
  user: SessionUser | null;
  /** True once a JWT session is active. */
  isAuthenticated: boolean;
  /** False during the first client render, before storage has been read. */
  hydrated: boolean;
  /** Adopt a freshly logged-in user (called by the login flow after setSession). */
  signIn: (user: SessionUser) => void;
  /** Drop the JWT session and fall back to the dev role. */
  signOut: () => void;
}

const RoleContext = createContext<RoleContextType | undefined>(undefined);

export function RoleProvider({ children }: { children: ReactNode }) {
  // Deterministic first paint on both server and client (storage is unreadable
  // during SSR); the effect below reconciles to the real stored identity.
  const [role, setRoleState] = useState<UserRole>(DEFAULT_ROLE);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const sessionUser = getSessionUser();
    if (sessionUser) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUser(sessionUser);
      setRoleState(sessionUser.role);
    } else {
      // Populate the dev-header fallback so client calls that don't thread a
      // role still carry one in a no-JWT environment.
      const devRole = getDevRole() ?? DEFAULT_ROLE;
      setRoleState(devRole);
      setDevRole(devRole);
    }
    setHydrated(true);
  }, []);

  const setRole = useCallback((next: UserRole) => {
    setRoleState(next);
    setDevRole(next);
  }, []);

  const signIn = useCallback((nextUser: SessionUser) => {
    setUser(nextUser);
    setRoleState(nextUser.role);
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
    const devRole = getDevRole() ?? DEFAULT_ROLE;
    setRoleState(devRole);
    setDevRole(devRole);
  }, []);

  return (
    <RoleContext.Provider
      value={{
        role,
        setRole,
        user,
        isAuthenticated: user !== null,
        hydrated,
        signIn,
        signOut,
      }}
    >
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  const context = useContext(RoleContext);
  if (context === undefined) {
    throw new Error("useRole must be used within a RoleProvider");
  }
  return context;
}
