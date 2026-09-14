"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LabelBadge } from "@/components/LabelBadge";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, listDocuments } from "@/lib/api/client";
import type { DocumentInventoryResponse } from "@/lib/api/types";
import { getSessionUser } from "@/lib/auth/session";
import { countLabeled, displayStage } from "@/lib/inventory";

/**
 * CISO fleet view: posture summary + links into agent deep-dive / audit.
 * Uses JWT when present; otherwise ciso via the DEV role header.
 */
export default function CisoPage() {
  const session = typeof window !== "undefined" ? getSessionUser() : null;
  const role = session?.role ?? "ciso";
  const [inventory, setInventory] = useState<DocumentInventoryResponse | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDocuments(role)
      .then(setInventory)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Network error")
      );
  }, [role]);

  const documents = inventory?.documents ?? [];
  const labeled = countLabeled(documents);
  const protectedCount = documents.filter(
    (d) => d.current_status === "protected"
  ).length;
  const pq = documents.filter((d) => d.profile_type === "post_quantum").length;
  const hybrid = documents.filter((d) => d.profile_type === "hybrid").length;

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">CISO posture</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              Fleet risk and protection summary
            </p>
          </div>
          <SiteNav active="/ciso" />
        </div>
      </header>
      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-6">
        {error && <p className="text-sm text-red-400">{error}</p>}
        {inventory && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Documents" value={inventory.count} />
            <Stat label="Labeled" value={labeled} />
            <Stat label="Protected" value={protectedCount} />
            <Stat label="PQ / Hybrid" value={`${pq} / ${hybrid}`} />
          </div>
        )}
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase text-[var(--color-text-muted)]">
              <tr>
                <th className="pb-2">Filename</th>
                <th className="pb-2">Label</th>
                <th className="pb-2">Trust</th>
                <th className="pb-2">Policy</th>
                <th className="pb-2">Profile</th>
                <th className="pb-2">Deep dive</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((row) => (
                <tr key={row.id} className="border-t border-[var(--color-border)]">
                  <td className="py-2 pr-3">{row.filename}</td>
                  <td className="py-2 pr-3">
                    {row.sensitivity_label ? (
                      <LabelBadge label={row.sensitivity_label} />
                    ) : (
                      "—"
                    )}
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
      <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
