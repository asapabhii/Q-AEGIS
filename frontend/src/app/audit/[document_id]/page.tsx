"use client";

import { useParams } from "next/navigation";
import React, { useEffect, useState, useCallback } from "react";
import { Link2, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

import Badge from "@/components/ui/Badge";
import HashDisplay from "@/components/ui/HashDisplay";
import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import { listAuditEntries, verifyAudit, ApiError } from "@/lib/api/client";
import type { AuditEntry, AuditVerifyResponse } from "@/lib/api/types";

import D3AuditChain from "@/components/ui/D3AuditChain";

export function AuditViewer({ documentId }: { documentId: string }) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const { role } = useRole();
  // The audit reads are gated server-side to VerifyChainCaller. Send the
  // caller's REAL role — never silently remap an unauthorized caller to a
  // privileged one — and render an honest 403 state when they lack access.
  const permitted = roleAllowed(ACCESS.audit, role);
  const [chain, setChain] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!permitted) {
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    listAuditEntries(documentId, role)
      .then((res) => {
        if (cancelled) return;
        setChain(res.entries);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setChain([]);
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, role, permitted]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => load(), [load]);

  const handleVerify = useCallback(async () => {
    if (chain.length === 0) return;
    setVerifying(true);
    setVerifyResult(null);
    setVerifyError(null);
    try {
      const result = await verifyAudit(documentId, role);
      setVerifyResult(result);
    } catch (err) {
      setVerifyError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setVerifying(false);
    }
  }, [chain.length, documentId, role]);

  const chainStatus: "valid" | "broken" | "unverified" =
    verifyResult === null
      ? "unverified"
      : verifyResult.is_valid
        ? "valid"
        : "broken";

  const StatusIcon = chainStatus === "valid" ? ShieldCheck : chainStatus === "broken" ? ShieldAlert : ShieldQuestion;
  const statusColor = chainStatus === "valid" ? "var(--status-pass)" : chainStatus === "broken" ? "var(--status-fail)" : "var(--status-pending)";

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={ACCESS.audit}
          resource="This document's forensic audit trail"
        />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="mx-auto w-full max-w-screen-xl space-y-8 px-6 py-8">
      {/* Page Header */}
      <header data-reveal>
        <div className="flex items-center gap-3 mb-1">
          <Link2 className="h-5 w-5" style={{ color: "var(--color-text-tertiary)" }} />
          <h1
            className="font-semibold"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            Cryptographic Audit Viewer
          </h1>
        </div>
        <p
          className="mono-data"
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Forensic inspection for document:{" "}
          <span style={{ color: "var(--color-text-primary)" }}>{documentId}</span>
        </p>
      </header>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-64" />
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => load()} />}

      {!loading && !error && (
        <>
          {/* Chain Integrity Check Card */}
          <div data-reveal className="card p-6 flex flex-wrap items-center justify-between gap-6" style={{ borderColor: chainStatus === "valid" ? "var(--status-pass)" : chainStatus === "broken" ? "var(--status-fail)" : "var(--color-border)" }}>
            <div className="flex items-center gap-4">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                style={{ 
                  backgroundColor: chainStatus === "valid" ? "rgba(16, 185, 129, 0.1)" : 
                                   chainStatus === "broken" ? "rgba(239, 68, 68, 0.1)" : 
                                   "var(--color-bg-tertiary)" 
                }}
              >
                <StatusIcon
                  className="h-5 w-5"
                  style={{ color: statusColor }}
                />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2
                    className="font-semibold"
                    style={{
                      fontSize: "var(--font-size-base)",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    Chain Integrity Check
                  </h2>
                  <Badge 
                    label={chainStatus === "valid" ? "Verified" : chainStatus === "broken" ? "Compromised" : "Unverified"} 
                    tone={chainStatus === "valid" ? "public" : chainStatus === "broken" ? "restricted" : "internal"} 
                    size="sm" 
                  />
                </div>
                <p
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  {chainStatus === "valid" && "Recomputed Merkle root matches the stored root - chain is intact"}
                  {chainStatus === "broken" && "Recomputed Merkle root does not match the stored root - audit chain compromised"}
                  {chainStatus === "unverified" && (chain.length === 0 ? "No audit entries found" : "Recomputes the Merkle prefix root server-side and compares it to the stored root")}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleVerify}
              disabled={verifying || chain.length === 0}
              className="btn btn-primary shrink-0"
            >
              {verifying ? "Verifying..." : "Verify Chain Integrity"}
            </button>
          </div>

          {verifyError && (
            <div data-reveal className="card p-6" style={{ borderColor: "var(--status-fail)" }}>
              <div className="flex items-center gap-3">
                <ShieldAlert className="h-5 w-5" style={{ color: "var(--status-fail)" }} />
                <p className="text-sm" style={{ color: "var(--status-fail)" }}>
                  Verification failed: {verifyError}
                </p>
              </div>
            </div>
          )}

          {verifyResult && (
            <div data-reveal className="card p-6 space-y-4">
              <h3
                className="font-semibold"
                style={{ fontSize: "var(--font-size-base)", color: "var(--color-text-primary)" }}
              >
                Server-Side Verification Result
              </h3>
              <dl className="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt
                    className="text-xs uppercase tracking-wider mb-1.5"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Recomputed Root
                  </dt>
                  <dd>
                    <HashDisplay hash={verifyResult.computed_root} />
                  </dd>
                </div>
                <div>
                  <dt
                    className="text-xs uppercase tracking-wider mb-1.5"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Stored Root
                  </dt>
                  <dd>
                    <HashDisplay hash={verifyResult.stored_root} />
                  </dd>
                </div>
                <div>
                  <dt
                    className="text-xs uppercase tracking-wider mb-1.5"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Tree Size
                  </dt>
                  <dd
                    className="mono-data text-sm"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {verifyResult.entry_count}
                  </dd>
                </div>
                <div>
                  <dt
                    className="text-xs uppercase tracking-wider mb-1.5"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    End Index
                  </dt>
                  <dd
                    className="mono-data text-sm"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {verifyResult.end_index}
                  </dd>
                </div>
              </dl>
              <p
                className="text-sm"
                style={{
                  color: verifyResult.is_valid ? "var(--status-pass)" : "var(--status-fail)",
                }}
              >
                {verifyResult.is_valid
                  ? "Recomputed root matches the stored root."
                  : "Recomputed root does not match the stored root."}
              </p>
            </div>
          )}

          {/* Audit Trail Timeline */}
          <div data-reveal className="card p-0 overflow-hidden">
            <div className="p-6 border-b border-hairline" style={{ borderColor: "var(--color-border)" }}>
               <h2
                 className="font-semibold mb-1"
                 style={{
                   fontSize: "var(--font-size-lg)",
                   color: "var(--color-text-primary)",
                 }}
               >
                 Cryptographic Audit Trail
               </h2>
               <p
                 style={{
                   fontSize: "var(--font-size-sm)",
                   color: "var(--color-text-secondary)",
                 }}
               >
                 Merkle-root visualization
               </p>
            </div>
            
            <div className="w-full bg-[var(--color-bg-primary)]">
              {chain.length > 0 ? (
                <D3AuditChain chain={chain} />
              ) : (
                <div className="p-6">
                  <EmptyState
                    icon={<Link2 className="h-8 w-8" />}
                    title="No audit blocks yet"
                    message="No cryptographic audit entries have been recorded for this document. Entries appear here as it moves through classification, risk, policy, and crypto stages."
                  />
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function AuditPage() {
  const params = useParams();
  const documentId = params?.document_id as string;
  
  if (!documentId) return null;
  
  return <AuditViewer documentId={documentId} />;
}
