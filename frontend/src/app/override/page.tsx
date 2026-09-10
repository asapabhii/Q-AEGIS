"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { LabelBadge } from "@/components/LabelBadge";
import { SiteNav } from "@/components/SiteNav";
import {
  ApiError,
  getDocument,
  overrideClassification,
} from "@/lib/api/client";
import type {
  DocumentSnapshot,
  ManualOverrideResponse,
  SensitivityLabel,
  UserRole,
} from "@/lib/api/types";
import {
  MIN_JUSTIFICATION_CHARS,
  SENSITIVITY_LABELS,
  canSubmitOverride,
  strippedJustificationLength,
} from "@/lib/override";

const OVERRIDE_ROLES: { value: UserRole; label: string }[] = [
  { value: "security_analyst", label: "Security Analyst" },
  { value: "security_admin", label: "Security Admin" },
  { value: "data_owner", label: "Data Owner" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

export function OverrideScreen({
  initialDocumentId = "",
}: {
  initialDocumentId?: string;
}) {
  const [role, setRole] = useState<UserRole>("security_analyst");
  const [documentId, setDocumentId] = useState(initialDocumentId);
  const [snapshot, setSnapshot] = useState<DocumentSnapshot | null>(null);
  const [newLabel, setNewLabel] = useState<SensitivityLabel | "">("");
  const [justification, setJustification] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<ManualOverrideResponse | null>(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(
    () => Boolean(initialDocumentId.trim())
  );
  const [submitting, setSubmitting] = useState(false);

  const loadSnapshot = useCallback(
    async (id: string, options?: { keepResult?: boolean }) => {
      setLoadingSnapshot(true);
      setLoadError(null);
      if (!options?.keepResult) {
        setResult(null);
      }
      try {
        const loaded = await getDocument(id.trim(), role);
        setSnapshot(loaded);
        setNewLabel("");
        setConfirmed(false);
      } catch (err) {
        setSnapshot(null);
        setLoadError(err instanceof ApiError ? err.message : "Network error");
      } finally {
        setLoadingSnapshot(false);
      }
    },
    [role]
  );

  useEffect(() => {
    const id = initialDocumentId.trim();
    if (!id) return;
    let cancelled = false;
    getDocument(id, role)
      .then((loaded) => {
        if (cancelled) return;
        setResult(null);
        setSnapshot(loaded);
        setNewLabel("");
        setConfirmed(false);
        setLoadError(null);
        setLoadingSnapshot(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSnapshot(null);
        setLoadError(err instanceof ApiError ? err.message : "Network error");
        setLoadingSnapshot(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialDocumentId, role]);

  const snapshotMatchesInput =
    snapshot !== null && snapshot.id === documentId.trim();
  const currentLabel = snapshotMatchesInput
    ? snapshot.sensitivity_label
    : null;
  const canSubmit = canSubmitOverride({
    documentId,
    loadedDocumentId: snapshot?.id ?? null,
    hasClassifiedSnapshot: currentLabel !== null,
    newLabel,
    currentLabel,
    justification,
    confirmed,
    loading: submitting || loadingSnapshot,
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !newLabel) return;
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    try {
      const saved = await overrideClassification(
        {
          document_id: documentId.trim(),
          new_label: newLabel,
          justification: justification.trim(),
        },
        role
      );
      setResult(saved);
      setConfirmed(false);
      await loadSnapshot(documentId, { keepResult: true });
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const justChars = strippedJustificationLength(justification);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold"
            >
              Q
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Manual Override
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                PRD.md FR-12 · permanently logged
              </p>
            </div>
          </div>
          <SiteNav active="/override" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-8">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <h2 className="text-base font-semibold mb-1">Override a classification</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Security Analysts and Security Admins can relabel a document. The
            server snapshots the current effective label. Confirmation is a
            UI gate — it is not sent to the API.
          </p>

          <form onSubmit={handleSubmit} className="grid gap-5 md:grid-cols-2">
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="override-role"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Caller Role
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    (authorization plumbing, not authentication)
                  </span>
                </label>
                <select
                  id="override-role"
                  value={role}
                  onChange={(event) => setRole(event.target.value as UserRole)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                >
                  {OVERRIDE_ROLES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="override-document-id"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Document ID
                </label>
                <div className="flex gap-2">
                  <input
                    id="override-document-id"
                    type="text"
                    value={documentId}
                    onChange={(event) => setDocumentId(event.target.value)}
                    className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono focus:border-[var(--color-border-focus)] focus:outline-none"
                    placeholder="UUID from classify or inventory"
                  />
                  <button
                    type="button"
                    id="override-load-btn"
                    onClick={() => void loadSnapshot(documentId)}
                    disabled={loadingSnapshot || !documentId.trim()}
                    className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loadingSnapshot ? "Loading…" : "Load"}
                  </button>
                </div>
              </div>

              <div>
                <label
                  htmlFor="override-new-label"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  New label
                </label>
                <select
                  id="override-new-label"
                  value={newLabel}
                  onChange={(event) =>
                    setNewLabel(event.target.value as SensitivityLabel | "")
                  }
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                >
                  <option value="">Select a label</option>
                  {SENSITIVITY_LABELS.map((label) => (
                    <option
                      key={label}
                      value={label}
                      disabled={label === currentLabel}
                    >
                      {label}
                      {label === currentLabel ? " (current)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="override-justification"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Justification
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    ({justChars}/{MIN_JUSTIFICATION_CHARS} after trim)
                  </span>
                </label>
                <textarea
                  id="override-justification"
                  value={justification}
                  onChange={(event) => setJustification(event.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none resize-y"
                  placeholder="Why this label is correct. At least 20 characters."
                />
              </div>

              <div className="flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3">
                <input
                  id="override-confirm"
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  className="mt-0.5 h-4 w-4"
                />
                <label htmlFor="override-confirm" className="text-sm leading-relaxed">
                  I confirm this action will be permanently logged
                </label>
              </div>

              <button
                type="submit"
                id="override-submit-btn"
                disabled={!canSubmit}
                className="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Submitting…" : "Submit override"}
              </button>

              {loadError && <p className="text-sm text-red-400">{loadError}</p>}
              {submitError && <p className="text-sm text-red-400">{submitError}</p>}
            </div>

            <div className="space-y-4">
              {snapshotMatchesInput && snapshot && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Current effective label
                  </h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">Filename</dt>
                      <dd>{snapshot.filename}</dd>
                    </div>
                    <div className="flex justify-between items-center">
                      <dt className="text-[var(--color-text-secondary)]">Label</dt>
                      <dd>
                        {snapshot.sensitivity_label ? (
                          <LabelBadge label={snapshot.sensitivity_label} />
                        ) : (
                          <span className="text-[var(--color-text-muted)]">
                            Not classified — cannot override
                          </span>
                        )}
                      </dd>
                    </div>
                    {snapshot.label_source && (
                      <div className="flex justify-between">
                        <dt className="text-[var(--color-text-secondary)]">Source</dt>
                        <dd className="font-mono text-xs">{snapshot.label_source}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              {result && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Override recorded
                  </h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <dt className="text-[var(--color-text-secondary)]">From</dt>
                      <dd>
                        <LabelBadge label={result.original_label} />
                      </dd>
                    </div>
                    <div className="flex justify-between items-center">
                      <dt className="text-[var(--color-text-secondary)]">To</dt>
                      <dd>
                        <LabelBadge label={result.new_label} />
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">ID</dt>
                      <dd className="font-mono text-xs">{result.id}</dd>
                    </div>
                  </dl>
                </div>
              )}

              {snapshot && !snapshotMatchesInput && (
                <div className="flex items-center justify-center h-48 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Document ID changed — load again
                </div>
              )}

              {!snapshot && !result && !loadError && (
                <div className="flex items-center justify-center h-48 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Load a classified document to override it
                </div>
              )}
            </div>
          </form>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>Q-AEGIS Shield · SPEC.md 3.13 · Input Screen 2</span>
          <span>Checkbox gates submit — confirmed is not an API field</span>
        </div>
      </footer>
    </div>
  );
}

function OverrideFromQuery() {
  const params = useSearchParams();
  const documentId = params.get("document_id") ?? "";
  return (
    <OverrideScreen key={documentId} initialDocumentId={documentId} />
  );
}

export default function OverridePage() {
  return (
    <Suspense
      fallback={
        <p className="p-6 text-sm text-[var(--color-text-muted)]">Loading…</p>
      }
    >
      <OverrideFromQuery />
    </Suspense>
  );
}
