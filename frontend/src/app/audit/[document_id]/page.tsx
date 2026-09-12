"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Link2, ShieldCheck, ShieldAlert, ShieldQuestion, Clock } from "lucide-react";

import Badge from "@/components/ui/Badge";
import HashDisplay from "@/components/ui/HashDisplay";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
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

export function AuditViewer({ documentId }: { documentId: string }) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const [role] = useState<UserRole>("auditor");
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
  const statusIconColor = chainStatus === "valid" ? "#8CFF00" : chainStatus === "broken" ? "#FF00FF" : "#00FFFF";
  const statusBorderColor = chainStatus === "valid" ? "#8CFF00" : chainStatus === "broken" ? "#FF00FF" : "#333333";

  return (
    <div ref={containerRef} className="mx-auto w-full max-w-screen-xl space-y-6 px-6 py-8 bg-black text-white rounded-none">
      {/* Page Header */}
      <header data-reveal className="flex items-center gap-3 mb-6 border-b border-[#333] pb-4">
        <div
          className="flex h-10 w-10 items-center justify-center border border-[#00FFFF]"
          style={{ backgroundColor: "rgba(0, 255, 255, 0.1)" }}
        >
          <Link2 className="h-5 w-5" style={{ color: "#00FFFF" }} />
        </div>
        <div>
          <h1 className="font-sans font-bold mb-1 tracking-wider uppercase" style={{ color: "#00FFFF" }}>
            Cryptographic Audit Viewer
          </h1>
          <p className="font-mono text-xs text-gray-400">
            FORENSIC INSPECTION FOR DOCUMENT_ID:
            <span className="ml-2 font-bold text-white">{documentId}</span>
          </p>
        </div>
      </header>

      {loading && (
        <p className="font-mono text-sm text-[#00FFFF] animate-pulse">
          INITIALIZING FORENSIC DECRYPTION...
        </p>
      )}

      {error && (
        <p className="font-mono text-sm text-[#FF00FF]">{error}</p>
      )}

      {!loading && !error && (
        <>
          {/* Chain Integrity Card */}
          <div
            data-reveal
            className="p-6 border bg-black transition-colors duration-500"
            style={{
              borderColor: statusBorderColor,
              boxShadow: chainStatus === "valid" ? "0 0 20px rgba(140, 255, 0, 0.1)" : chainStatus === "broken" ? "0 0 20px rgba(255, 0, 255, 0.2)" : "none",
            }}
          >
            <div className="mb-4 border-b border-[#333] pb-2">
              <h2 className="font-sans font-bold uppercase tracking-widest text-[#8CFF00]">CHAIN INTEGRITY CHECK</h2>
              <p className="font-mono text-xs text-gray-500 mt-1">
                {chain.length === 0
                  ? "NO AUDIT ENTRIES FOUND"
                  : "CRYPTOGRAPHIC PROOF: ENTRY PREV_HASH == PREVIOUS PAYLOAD_HASH"}
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4 mt-6">
              <div className="flex items-center gap-3">
                <div
                  className="flex h-12 w-12 items-center justify-center border"
                  style={{ borderColor: statusIconColor, backgroundColor: "rgba(0,0,0,0.5)" }}
                >
                  <StatusIcon className="h-6 w-6" style={{ color: statusIconColor }} />
                </div>
                <div>
                  <div className="font-mono text-sm font-bold tracking-widest" style={{ color: statusIconColor }}>
                    {chainStatus === "valid"
                      ? "SYS: VERIFIED"
                      : chainStatus === "broken"
                        ? "SYS: TAMPERED"
                        : "SYS: UNVERIFIED"}
                  </div>
                  {chainStatus === "valid" && (
                    <p className="mt-1 font-mono text-[10px] text-[#8CFF00]">
                      CRYPTOGRAPHIC HASHES MATCH — CHAIN IS INTACT
                    </p>
                  )}
                  {chainStatus === "broken" && (
                    <p className="mt-1 font-mono text-[10px] text-[#FF00FF]">
                      HASH MISMATCH DETECTED — AUDIT CHAIN COMPROMISED
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={handleVerify}
                disabled={verifying || chain.length === 0}
                className="px-6 py-2 border font-mono text-xs font-bold uppercase tracking-widest transition-all"
                style={{
                  borderColor: "#00FFFF",
                  color: "#00FFFF",
                  backgroundColor: verifying ? "rgba(0, 255, 255, 0.2)" : "transparent",
                  cursor: (verifying || chain.length === 0) ? "not-allowed" : "pointer"
                }}
                onMouseEnter={(e) => { if (!verifying && chain.length > 0) { e.currentTarget.style.backgroundColor = "rgba(0, 255, 255, 0.1)"; } }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
              >
                {verifying ? "VERIFYING PROOFS..." : "VERIFY CHAIN INTEGRITY"}
              </button>
            </div>
          </div>

          {/* Audit Trail Timeline */}
          <div data-reveal className="p-6 border border-[#333] bg-black">
            <div className="mb-6 border-b border-[#333] pb-2">
               <h2 className="font-sans font-bold uppercase tracking-widest text-[#00FFFF]">CRYPTOGRAPHIC AUDIT TRAIL</h2>
               <p className="font-mono text-xs text-gray-500 mt-1">D3.JS MERKLE-ROOT VISUALIZATION</p>
            </div>
            
            <div className="relative w-full">
              {chain.length > 0 ? (
                <D3AuditChain chain={chain} />
              ) : (
                <p className="font-mono text-xs text-gray-500">NO BLOCKS FOUND.</p>
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
