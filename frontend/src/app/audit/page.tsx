"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, listAuditEntries, verifyAudit } from "@/lib/api/client";
import type {
  AuditChainResponse,
  AuditVerifyResponse,
  UserRole,
} from "@/lib/api/types";

const AUDIT_ROLES: { value: UserRole; label: string }[] = [
  { value: "auditor", label: "Auditor" },
  { value: "security_admin", label: "Security Admin" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "data_owner", label: "Data Owner" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

export function AuditScreen({
  initialDocumentId = "",
}: {
  initialDocumentId?: string;
}) {
  const [role, setRole] = useState<UserRole>("auditor");
  const [documentId, setDocumentId] = useState(initialDocumentId);
  const [chain, setChain] = useState<AuditChainResponse | null>(null);
  const [verdict, setVerdict] = useState<AuditVerifyResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [loadingChain, setLoadingChain] = useState(
    () => Boolean(initialDocumentId.trim())
  );
  const [verifying, setVerifying] = useState(false);

  const trimmedId = documentId.trim();
  const chainMatches = chain !== null && chain.document_id === trimmedId;
  const verdictMatches =
    verdict !== null && verdict.document_id === trimmedId;
  const canQuery = Boolean(trimmedId) && !loadingChain && !verifying;

  useEffect(() => {
    const id = initialDocumentId.trim();
    if (!id) return;
    let cancelled = false;
    listAuditEntries(id, role)
      .then((loaded) => {
        if (cancelled) return;
        setChain(loaded);
        setVerdict(null);
        setLoadError(null);
        setLoadingChain(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setChain(null);
        setLoadError(err instanceof ApiError ? err.message : "Network error");
        setLoadingChain(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialDocumentId, role]);

  async function handleLoad() {
    if (!trimmedId) return;
    setLoadingChain(true);
    setLoadError(null);
    setVerdict(null);
    try {
      setChain(await listAuditEntries(trimmedId, role));
    } catch (err) {
      setChain(null);
      setLoadError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setLoadingChain(false);
    }
  }

  async function handleVerify() {
    if (!trimmedId) return;
    setVerifying(true);
    setVerifyError(null);
    try {
      setVerdict(await verifyAudit(trimmedId, role));
    } catch (err) {
      setVerdict(null);
      setVerifyError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setVerifying(false);
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
                Audit Viewer
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                PRD.md FR-15 · list does not judge the chain
              </p>
            </div>
          </div>
          <SiteNav active="/audit" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-6">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <h2 className="text-base font-semibold mb-1">One document&apos;s chain</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Load lists entries genesis first. Verify recomputes the Merkle
            prefix in a separate call. The list has no validity flag.
          </p>

          <div className="grid gap-4 md:grid-cols-2 mb-6">
            <div>
              <label
                htmlFor="audit-role"
                className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
              >
                Caller Role
                <span className="ml-1 text-[var(--color-text-muted)]">
                  (authorization plumbing, not authentication)
                </span>
              </label>
              <select
                id="audit-role"
                value={role}
                onChange={(event) => setRole(event.target.value as UserRole)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
              >
                {AUDIT_ROLES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="audit-document-id"
                className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
              >
                Document ID
              </label>
              <input
                id="audit-document-id"
                type="text"
                value={documentId}
                onChange={(event) => {
                  setDocumentId(event.target.value);
                  setVerdict(null);
                  setVerifyError(null);
                }}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm font-mono focus:border-[var(--color-border-focus)] focus:outline-none"
                placeholder="UUID"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3 mb-6">
            <button
              type="button"
              id="audit-load-btn"
              onClick={() => void handleLoad()}
              disabled={!canQuery}
              className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingChain ? "Loading…" : "Load chain"}
            </button>
            <button
              type="button"
              id="audit-verify-btn"
              onClick={() => void handleVerify()}
              disabled={!canQuery}
              className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold hover:bg-[var(--color-bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {verifying ? "Verifying…" : "Verify chain"}
            </button>
          </div>

          {loadError && <p className="text-sm text-red-400 mb-4">{loadError}</p>}
          {verifyError && (
            <p className="text-sm text-red-400 mb-4">{verifyError}</p>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              {chainMatches && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Chain ({chain.count})
                  </h3>
                  {chain.count === 0 ? (
                    <p className="text-sm text-[var(--color-text-muted)]">
                      No entries for this document
                    </p>
                  ) : (
                    <ol className="space-y-2 text-xs">
                      {chain.entries.map((entry) => (
                        <li
                          key={entry.id}
                          className="rounded-md border border-[var(--color-border)] px-2 py-2 space-y-2"
                        >
                          <div className="flex justify-between gap-2">
                            <span className="font-mono">{entry.index}</span>
                            <span>{entry.event_type}</span>
                          </div>
                          <dl className="space-y-1 text-[var(--color-text-muted)]">
                            <div className="flex justify-between gap-2">
                              <dt>Actor</dt>
                              <dd className="font-mono break-all">
                                {entry.actor_id ?? "—"}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt>Created</dt>
                              <dd className="font-mono break-all">
                                {entry.created_at}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt>Prev hash</dt>
                              <dd className="font-mono break-all">
                                {entry.prev_hash ?? "—"}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt>Payload hash</dt>
                              <dd className="font-mono break-all">
                                {entry.payload_hash}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-2">
                              <dt>Merkle root</dt>
                              <dd className="font-mono break-all">
                                {entry.merkle_root_at_time}
                              </dd>
                            </div>
                          </dl>
                          <details>
                            <summary className="cursor-pointer text-[var(--color-text-secondary)]">
                              Payload
                            </summary>
                            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-[var(--color-text-muted)]">
                              {JSON.stringify(entry.payload, null, 2)}
                            </pre>
                          </details>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              )}

              {chain && !chainMatches && (
                <p className="text-sm text-[var(--color-text-muted)]">
                  Document ID changed — load again
                </p>
              )}

              {!chain && !loadError && (
                <div className="flex items-center justify-center h-40 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Load a document to see its chain
                </div>
              )}
            </div>

            <div>
              {verdictMatches && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Independent verification
                  </h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Valid
                      </dt>
                      <dd>{verdict.is_valid ? "yes" : "no"}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--color-text-secondary)]">
                        Computed
                      </dt>
                      <dd className="font-mono text-xs break-all">
                        {verdict.computed_root}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--color-text-secondary)]">
                        Stored
                      </dt>
                      <dd className="font-mono text-xs break-all">
                        {verdict.stored_root}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Entries
                      </dt>
                      <dd>{verdict.entry_count}</dd>
                    </div>
                  </dl>
                </div>
              )}

              {!verdictMatches && !verifyError && (
                <div className="flex items-center justify-center h-40 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Verify is a separate request
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>Q-AEGIS Shield · SPEC.md 3.13 · Output Screen 2</span>
          <span>is_valid lives on verify, not on the list</span>
        </div>
      </footer>
    </div>
  );
}

function AuditFromQuery() {
  const params = useSearchParams();
  const documentId = params.get("document_id") ?? "";
  return <AuditScreen key={documentId} initialDocumentId={documentId} />;
}

export default function AuditPage() {
  return (
    <Suspense
      fallback={
        <p className="p-6 text-sm text-[var(--color-text-muted)]">Loading…</p>
      }
    >
      <AuditFromQuery />
    </Suspense>
  );
}
