"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, checkHealth, listDocuments } from "@/lib/api/client";
import type { DocumentInventoryResponse, HealthResponse } from "@/lib/api/types";
import { getSessionUser } from "@/lib/auth/session";

/**
 * Engineer ops view: health, inventory counts, links to classify/upload path.
 */
export default function EngineerPage() {
  const session = typeof window !== "undefined" ? getSessionUser() : null;
  const role = session?.role ?? "engineer";
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [inventory, setInventory] = useState<DocumentInventoryResponse | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([checkHealth(), listDocuments(role)])
      .then(([h, inv]) => {
        setHealth(h);
        setInventory(inv);
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Network error")
      );
  }, [role]);

  const statuses = inventory?.documents.reduce<Record<string, number>>(
    (acc, doc) => {
      acc[doc.current_status] = (acc[doc.current_status] ?? 0) + 1;
      return acc;
    },
    {}
  );

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">Engineer ops</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              Service health and document pipeline stages
            </p>
          </div>
          <SiteNav active="/engineer" />
        </div>
      </header>
      <main className="flex-1 mx-auto w-full max-w-3xl px-6 py-8 space-y-6">
        {error && <p className="text-sm text-red-400">{error}</p>}
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 space-y-2">
          <h2 className="font-semibold">API health</h2>
          {health ? (
            <p className="text-sm font-mono">
              {health.status} · {health.service} · {health.version}
            </p>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">Checking…</p>
          )}
        </section>
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 space-y-3">
          <h2 className="font-semibold">Lifecycle counts</h2>
          {statuses ? (
            <ul className="text-sm space-y-1 font-mono">
              {Object.entries(statuses).map(([status, count]) => (
                <li key={status}>
                  {status}: {count}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">Loading…</p>
          )}
          <Link href="/" className="text-cyan-400 text-sm hover:underline">
            Open classify / upload →
          </Link>
        </section>
      </main>
    </div>
  );
}
