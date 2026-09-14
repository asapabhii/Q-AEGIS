"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LabelBadge } from "@/components/LabelBadge";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, listDocuments, subscribeEvents } from "@/lib/api/client";
import type { DocumentInventoryResponse, UserRole } from "@/lib/api/types";
import { getAccessToken, getSessionUser, setDevRole } from "@/lib/auth/session";
import { countLabeled, displayStage } from "@/lib/inventory";

const DASHBOARD_ROLES: { value: UserRole; label: string }[] = [
  { value: "security_admin", label: "Security Admin" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

export function DashboardScreen() {
  const session = typeof window !== "undefined" ? getSessionUser() : null;
  const hasJwt = typeof window !== "undefined" && Boolean(getAccessToken());
  const [role, setRole] = useState<UserRole>(
    session?.role && DASHBOARD_ROLES.some((r) => r.value === session.role)
      ? session.role
      : "security_admin"
  );
  const [inventory, setInventory] = useState<DocumentInventoryResponse | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (!hasJwt) setDevRole(role);
  }, [role, hasJwt]);

  useEffect(() => {
    let cancelled = false;
    listDocuments(role)
      .then((loaded) => {
        if (cancelled) return;
        setInventory(loaded);
        setError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setInventory(null);
        setError(err instanceof ApiError ? err.message : "Network error");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role]);

  useEffect(() => {
    const stop = subscribeEvents((eventName) => {
      if (eventName === "ready") {
        setLive(true);
        return;
      }
      if (eventName === "inventory" || eventName === "bus") {
        void listDocuments(role)
          .then((loaded) => setInventory(loaded))
          .catch(() => undefined);
      }
      if (eventName === "error") setLive(false);
    }, role);
    return stop;
  }, [role]);

  function handleRefresh() {
    setLoading(true);
    setError(null);
    void listDocuments(role)
      .then((loaded) => {
        setInventory(loaded);
        setError(null);
      })
      .catch((err: unknown) => {
        setInventory(null);
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => setLoading(false));
  }

  const documents = inventory?.documents ?? [];
  const labeled = countLabeled(documents);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold"
            >
              Q
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Risk Dashboard
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                FR-14 · {live ? "live updates on" : "connecting…"}
              </p>
            </div>
          </div>
          <SiteNav active="/dashboard" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-6">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
            <div>
              <h2 className="text-base font-semibold mb-1">
                Monitored documents
              </h2>
              <p className="text-sm text-[var(--color-text-muted)]">
                Stage fields stay empty until that step has run.
              </p>
            </div>
            <div className="flex items-end gap-3">
              {!hasJwt && (
                <div>
                  <label
                    htmlFor="dashboard-role"
                    className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                  >
                    Caller Role
                  </label>
                  <select
                    id="dashboard-role"
                    value={role}
                    onChange={(event) =>
                      setRole(event.target.value as UserRole)
                    }
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
                  >
                    {DASHBOARD_ROLES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button
                type="button"
                id="dashboard-refresh-btn"
                onClick={handleRefresh}
                disabled={loading}
                className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {loading ? "Loading…" : "Refresh"}
              </button>
            </div>
          </div>

          {error && <p className="text-sm text-red-400 mb-4">{error}</p>}

          {inventory && inventory.count === 0 && (
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              No documents registered
            </p>
          )}

          {inventory && (
            <div className="grid grid-cols-2 gap-3 mb-6 sm:grid-cols-3">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
                <div className="text-xs text-[var(--color-text-muted)]">
                  Documents
                </div>
                <div className="text-lg font-semibold">{inventory.count}</div>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
                <div className="text-xs text-[var(--color-text-muted)]">
                  With a label
                </div>
                <div className="text-lg font-semibold">{labeled}</div>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
                <div className="text-xs text-[var(--color-text-muted)]">
                  Not yet labeled
                </div>
                <div className="text-lg font-semibold">
                  {inventory.count - labeled}
                </div>
              </div>
            </div>
          )}

          {documents.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
                  <tr>
                    <th className="pb-2 pr-3 font-medium">Filename</th>
                    <th className="pb-2 pr-3 font-medium">Status</th>
                    <th className="pb-2 pr-3 font-medium">Label</th>
                    <th className="pb-2 pr-3 font-medium">Risk</th>
                    <th className="pb-2 pr-3 font-medium">Trust</th>
                    <th className="pb-2 pr-3 font-medium">Policy</th>
                    <th className="pb-2 pr-3 font-medium">Profile</th>
                    <th className="pb-2 font-medium">Open</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((row) => (
                    <tr
                      key={row.id}
                      className="border-t border-[var(--color-border)]"
                    >
                      <td className="py-2 pr-3">{row.filename}</td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {row.current_status}
                      </td>
                      <td className="py-2 pr-3">
                        {row.sensitivity_label ? (
                          <LabelBadge label={row.sensitivity_label} />
                        ) : (
                          <span className="text-[var(--color-text-muted)]">
                            —
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {displayStage(row.risk_value)}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {displayStage(row.trust_score)}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {displayStage(row.final_decision)}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {displayStage(row.profile_type)}
                      </td>
                      <td className="py-2 space-x-3 whitespace-nowrap">
                        <Link
                          href={`/agents?document_id=${row.id}`}
                          className="text-cyan-400 hover:underline"
                        >
                          Agents
                        </Link>
                        <Link
                          href={`/audit?document_id=${row.id}`}
                          className="text-cyan-400 hover:underline"
                        >
                          Audit
                        </Link>
                        <Link
                          href={`/override?document_id=${row.id}`}
                          className="text-cyan-400 hover:underline"
                        >
                          Override
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return <DashboardScreen />;
}
