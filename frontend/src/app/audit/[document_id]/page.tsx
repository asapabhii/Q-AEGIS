"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Link2, ShieldCheck, ShieldAlert, ShieldQuestion, Clock } from "lucide-react";

import Badge from "@/components/ui/Badge";
import HashDisplay from "@/components/ui/HashDisplay";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import { listAuditEntries, ApiError } from "@/lib/api/client";
import type { AuditEntry, UserRole } from "@/lib/api/types";

function verifyChain(chain: AuditEntry[]): boolean {
  for (let i = 0; i < chain.length; i += 1) {
    if (i > 0 && chain[i].prev_hash !== chain[i - 1].payload_hash) {
      return false;
    }
  }
  if (chain.length > 0 && chain[0].prev_hash !== null) {
    return false;
  }
  return true;
}

function formatPayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}

import D3AuditChain from "@/components/ui/D3AuditChain";

const AUDIT_ALLOWED_ROLES: UserRole[] = ["security_admin", "auditor", "ciso"];

export function AuditViewer({ documentId }: { documentId: string }) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const { role: contextRole } = useRole();
  const role = AUDIT_ALLOWED_ROLES.includes(contextRole) ? contextRole : "auditor";
  const [chain, setChain] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
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
  }, [documentId, role]);

  const handleVerify = useCallback(() => {
    if (chain.length === 0) return;
    setVerifying(true);
    setVerified(null);
    const timer = window.setTimeout(() => {
      setVerified(verifyChain(chain));
      setVerifying(false);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [chain]);

  const chainStatus: "valid" | "broken" | "unverified" =
    chain.length === 0
      ? "unverified"
      : verified
        ? "valid"
        : verified === false
          ? "broken"
          : "unverified";

  const StatusIcon = chainStatus === "valid" ? ShieldCheck : chainStatus === "broken" ? ShieldAlert : ShieldQuestion;
  const statusColor = chainStatus === "valid" ? "var(--status-pass)" : chainStatus === "broken" ? "var(--status-fail)" : "var(--status-pending)";

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
        <div className="flex items-center justify-center min-h-[200px]">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Loading audit trail...
          </p>
        </div>
      )}

      {error && (
        <div className="card p-6" style={{ borderColor: "var(--status-fail)" }}>
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5" style={{ color: "var(--status-fail)" }} />
            <p className="text-sm" style={{ color: "var(--status-fail)" }}>
              {error}
            </p>
          </div>
        </div>
      )}

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
                  {chainStatus === "valid" && "Cryptographic hashes match - chain is intact"}
                  {chainStatus === "broken" && "Hash mismatch detected - audit chain compromised"}
                  {chainStatus === "unverified" && (chain.length === 0 ? "No audit entries found" : "Cryptographic proof: entry prev_hash == previous payload_hash")}
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
                  <p className="mono-data" style={{ color: "var(--color-text-tertiary)" }}>No blocks found.</p>
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
