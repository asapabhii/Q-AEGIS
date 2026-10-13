"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, FileText, Trash2 } from "lucide-react";

import NotPermitted from "@/components/ui/NotPermitted";
import { ErrorState } from "@/components/ui/states";
import {
  ApiError,
  downloadDocumentSummary,
  shredDocument,
} from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type { ShredResponse } from "@/lib/api/types";

const PAGE_ALLOWED = ACCESS.summaryPage;

export function SummaryScreen({
  initialDocumentId = "",
}: {
  initialDocumentId?: string;
}) {
  const { role } = useRole();
  const permitted = roleAllowed(PAGE_ALLOWED, role);
  const canExportRole = roleAllowed(ACCESS.export, role);
  const canShredRole = roleAllowed(ACCESS.shred, role);
  const [documentId, setDocumentId] = useState(initialDocumentId);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shredResult, setShredResult] = useState<ShredResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const trimmed = documentId.trim();
  const canExport = Boolean(trimmed) && canExportRole && !busy;
  const canShred = Boolean(trimmed) && canShredRole && confirmed && !busy;

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

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={PAGE_ALLOWED}
          resource="Export and shred"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8 space-y-8">
      <header>
        <h1
          className="font-semibold mb-1"
          style={{
            fontSize: "var(--font-size-2xl)",
            color: "var(--color-text-primary)",
          }}
        >
          Export &amp; Shred
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Export a document&apos;s full assessment, or crypto-shred its keys to
          make ciphertext permanently unreadable
        </p>
      </header>

      <div className="card p-5">
        <label className="block">
          <span
            className="block text-xs uppercase tracking-wider mb-2"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Document ID
          </span>
          <input
            className="input mono-data w-full"
            value={documentId}
            onChange={(e) => {
              setDocumentId(e.target.value);
              setShredResult(null);
              setConfirmed(false);
            }}
            placeholder="Enter document UUID..."
          />
        </label>
      </div>

      <section className="card p-5 space-y-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4" style={{ color: "var(--color-text-secondary)" }} />
          <h2
            className="text-sm font-semibold"
            style={{ color: "var(--color-text-primary)" }}
          >
            Export summary
          </h2>
        </div>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          CSV or PDF of classification, risk, agents, trust, policy, and crypto.
          {canExportRole
            ? ""
            : " Requires Data Owner or Security Admin — you can shred but not export as this role."}
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            disabled={!canExport}
            onClick={() => void handleExport("csv")}
            className="btn btn-secondary"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
          <button
            type="button"
            disabled={!canExport}
            onClick={() => void handleExport("pdf")}
            className="btn btn-secondary"
          >
            <Download className="h-4 w-4" />
            PDF
          </button>
        </div>
      </section>

      <section
        className="card p-5 space-y-3"
        style={{ borderColor: "var(--status-fail)" }}
      >
        <div className="flex items-center gap-2">
          <Trash2 className="h-4 w-4" style={{ color: "var(--status-fail)" }} />
          <h2
            className="text-sm font-semibold"
            style={{ color: "var(--color-text-primary)" }}
          >
            Crypto-shred
          </h2>
        </div>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          Destroys wrapped DEKs so ciphertext becomes permanently unreadable. The
          audit trail is kept. This is irreversible.
          {canShredRole
            ? ""
            : " Requires Data Owner, Compliance Officer, or Security Admin."}
        </p>
        <label
          className="flex items-start gap-2 text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            disabled={!canShredRole}
            className="mt-0.5"
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
          className="btn"
          style={{
            borderColor: "var(--status-fail)",
            color: "var(--status-fail)",
          }}
        >
          <Trash2 className="h-4 w-4" />
          Shred keys
        </button>
        {shredResult && (
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Shredded {shredResult.ciphertext_count} ciphertext row(s); newly
            destroyed {shredResult.newly_destroyed}
            {shredResult.already_shredded ? " (already shredded)" : ""}.
          </p>
        )}
      </section>

      {error && <ErrorState message={error} />}
    </div>
  );
}

export default function SummaryPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-3xl px-6 py-8 text-sm">Loading…</div>
      }
    >
      <SummaryPageInner />
    </Suspense>
  );
}

function SummaryPageInner() {
  const params = useSearchParams();
  return <SummaryScreen initialDocumentId={params.get("document_id") ?? ""} />;
}
