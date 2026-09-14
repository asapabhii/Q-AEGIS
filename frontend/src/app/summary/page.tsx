"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";
import {
  ApiError,
  downloadDocumentSummary,
  shredDocument,
} from "@/lib/api/client";
import type { ShredResponse, UserRole } from "@/lib/api/types";

const SUMMARY_ROLES: { value: UserRole; label: string }[] = [
  { value: "data_owner", label: "Data Owner" },
  { value: "security_admin", label: "Security Admin" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "auditor", label: "Auditor" },
];

const SHRED_ROLES = new Set<UserRole>([
  "data_owner",
  "compliance_officer",
  "security_admin",
]);

const EXPORT_ROLES = new Set<UserRole>(["data_owner", "security_admin"]);

export function SummaryScreen({
  initialDocumentId = "",
}: {
  initialDocumentId?: string;
}) {
  const [role, setRole] = useState<UserRole>("data_owner");
  const [documentId, setDocumentId] = useState(initialDocumentId);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shredResult, setShredResult] = useState<ShredResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const trimmed = documentId.trim();
  const canExport = Boolean(trimmed) && EXPORT_ROLES.has(role) && !busy;
  const canShred =
    Boolean(trimmed) && SHRED_ROLES.has(role) && confirmed && !busy;

  async function handleExport(format: "csv" | "pdf") {
    if (!canExport) return;
    setBusy(true);
    setError(null);
    try {
      await downloadDocumentSummary(trimmed, format, role);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  async function handleShred() {
    if (!canShred) return;
    setBusy(true);
    setError(null);
    setShredResult(null);
    try {
      setShredResult(
        await shredDocument({ document_id: trimmed, confirmed: true }, role)
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

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
                Document summary
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                FR-16 export and FR-8 crypto-shredding
              </p>
            </div>
          </div>
          <SiteNav active="/summary" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-8 space-y-8">
        <label className="block text-sm">
          <span className="text-[var(--color-text-secondary)]">Caller role</span>
          <select
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
          >
            {SUMMARY_ROLES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="text-[var(--color-text-secondary)]">Document id</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 font-mono text-sm"
            value={documentId}
            onChange={(e) => {
              setDocumentId(e.target.value);
              setShredResult(null);
              setConfirmed(false);
            }}
            placeholder="uuid"
          />
        </label>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Export summary</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            CSV or PDF of classification, risk, agents, trust, policy, and
            crypto. Requires data_owner or security_admin.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              disabled={!canExport}
              onClick={() => void handleExport("csv")}
              className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Download CSV
            </button>
            <button
              type="button"
              disabled={!canExport}
              onClick={() => void handleExport("pdf")}
              className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Download PDF
            </button>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Crypto-shred</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Destroys wrapped DEKs so ciphertext becomes permanently unreadable.
            Audit trail is kept. Irreversible.
          </p>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-1"
            />
            <span>
              I understand this permanently destroys decryption keys for this
              document and cannot be undone.
            </span>
          </label>
          <button
            type="button"
            disabled={!canShred}
            onClick={() => void handleShred()}
            className="rounded-lg border border-red-500/50 px-4 py-2 text-sm font-semibold text-red-300 disabled:opacity-50"
          >
            Shred keys
          </button>
          {shredResult && (
            <p className="text-xs text-[var(--color-text-secondary)]">
              Shredded {shredResult.ciphertext_count} ciphertext row(s);
              newly destroyed {shredResult.newly_destroyed}
              {shredResult.already_shredded ? " (already shredded)" : ""}.
            </p>
          )}
        </section>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </main>
    </div>
  );
}

export default function SummaryPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm">Loading…</div>}>
      <SummaryPageInner />
    </Suspense>
  );
}

function SummaryPageInner() {
  const params = useSearchParams();
  return (
    <SummaryScreen initialDocumentId={params.get("document_id") ?? ""} />
  );
}
