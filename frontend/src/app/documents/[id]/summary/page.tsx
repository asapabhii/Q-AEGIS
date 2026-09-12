"use client";

import { useEffect, useState } from "react";
import { FileText, Printer } from "lucide-react";

import Badge from "@/components/ui/Badge";
import HashDisplay from "@/components/ui/HashDisplay";
import RiskGauge from "@/components/ui/RiskGauge";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { getDocument, ApiError } from "@/lib/api/client";
import type {
  CryptoProfileType,
  DocumentSnapshot,
  SensitivityLabel,
  UserRole,
} from "@/lib/api/types";

const LABEL_TONES: Record<
  SensitivityLabel,
  "public" | "internal" | "confidential" | "restricted"
> = {
  PUBLIC: "public",
  INTERNAL: "internal",
  CONFIDENTIAL: "confidential",
  RESTRICTED: "restricted",
};

const PROFILE_TONES: Record<CryptoProfileType, "aes" | "hybrid" | "pqc"> = {
  aes256: "aes",
  hybrid: "hybrid",
  post_quantum: "pqc",
};

const PROFILE_LABELS: Record<CryptoProfileType, string> = {
  aes256: "AES-256",
  hybrid: "Hybrid X25519MLKEM768",
  post_quantum: "Full PQC",
};

export default function DocumentSummaryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const [role] = useState<UserRole>("security_admin");
  const [documentId, setDocumentId] = useState<string>("");

  useEffect(() => {
    params.then((p) => setDocumentId(p.id));
  }, [params]);

  const [snapshot, setSnapshot] = useState<DocumentSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    getDocument(documentId, role)
      .then((doc) => {
        if (cancelled) return;
        setSnapshot(doc);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSnapshot(null);
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, role]);

  const riskValue = snapshot?.risk_value !== null && snapshot?.risk_value !== undefined
    ? Number(snapshot.risk_value)
    : null;
  const trustValue = snapshot?.trust_score !== null && snapshot?.trust_score !== undefined
    ? Number(snapshot.trust_score)
    : null;

  return (
    <div ref={containerRef} className="mx-auto w-full max-w-4xl space-y-6 px-6 py-8 bg-black text-white rounded-none print:py-0 print:px-0 print:space-y-4 print:bg-white print:text-black">
      {/* Page Header */}
      <div data-reveal className="flex flex-col sm:flex-row items-start justify-between gap-4 mb-6 border-b border-[#333] pb-4 print:mb-2 print:border-black">
        <div className="flex items-center gap-3">
          <div
            className="flex h-12 w-12 items-center justify-center border border-[#FF00FF] print:hidden"
            style={{ backgroundColor: "rgba(255, 0, 255, 0.1)" }}
          >
            <FileText className="h-6 w-6" style={{ color: "#FF00FF" }} />
          </div>
          <div>
            <h1 className="font-sans font-bold uppercase tracking-widest text-[#FF00FF] print:text-black print:text-xl">
              Document Summary Report
            </h1>
            <p className="font-mono text-xs text-gray-400 mt-1 print:text-gray-700">
              EXPORTABLE ASSESSMENT FOR DOC_ID:
              <span className="ml-2 font-bold text-white print:text-black">{documentId}</span>
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex shrink-0 items-center gap-2 px-4 py-2 border font-mono text-xs font-bold uppercase tracking-widest transition-all print:hidden"
          style={{
            borderColor: "#FF00FF",
            color: "#FF00FF",
            backgroundColor: "transparent"
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(255, 0, 255, 0.1)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
        >
          <Printer className="h-4 w-4" />
          PRINT PDF
        </button>
      </div>

      {loading && (
        <p className="font-mono text-sm text-[#FF00FF] animate-pulse">
          FETCHING DOCUMENT SNAPSHOT...
        </p>
      )}

      {error && (
        <p className="font-mono text-sm text-red-500">{error}</p>
      )}

      {!loading && !error && snapshot && (
        <>
          <div data-reveal className="grid gap-6 md:grid-cols-2 print:gap-4 print:grid-cols-1">
            {/* Classification Card */}
            <div className="p-6 border border-[#333] bg-black print:border-black print:bg-white hover:border-[#8CFF00] transition-colors duration-300">
              <h2 className="font-sans font-bold uppercase tracking-widest text-[#8CFF00] mb-4 print:text-black">CLASSIFICATION</h2>
              <dl className="space-y-4 text-sm font-mono">
                <div className="flex items-center justify-between pb-3 border-b border-[#333] print:border-gray-300">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">LABEL</dt>
                  <dd>
                    {snapshot.sensitivity_label ? (
                      <Badge
                        label={snapshot.sensitivity_label}
                        tone={LABEL_TONES[snapshot.sensitivity_label]}
                      />
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </dd>
                </div>
                <div className="flex justify-between pb-3 border-b border-[#333] print:border-gray-300">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">SOURCE</dt>
                  <dd className="font-bold text-[#8CFF00] print:text-black">
                    {snapshot.label_source ?? "—"}
                  </dd>
                </div>
                <div className="flex justify-between pb-1">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">OVERRIDE ID</dt>
                  <dd>
                    {snapshot.override_id ? (
                      <HashDisplay hash={snapshot.override_id} />
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Protection Profile Card */}
            <div className="p-6 border border-[#333] bg-black print:border-black print:bg-white hover:border-[#00FFFF] transition-colors duration-300">
              <h2 className="font-sans font-bold uppercase tracking-widest text-[#00FFFF] mb-4 print:text-black">PROTECTION PROFILE</h2>
              <dl className="space-y-4 text-sm font-mono">
                <div className="flex items-center justify-between pb-3 border-b border-[#333] print:border-gray-300">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">PROFILE</dt>
                  <dd>
                    {snapshot.profile_type ? (
                      <Badge
                        label={PROFILE_LABELS[snapshot.profile_type]}
                        tone={PROFILE_TONES[snapshot.profile_type]}
                      />
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </dd>
                </div>
                <div className="flex justify-between pb-3">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">DECISION</dt>
                  <dd className="font-bold text-[#00FFFF] print:text-black uppercase">
                    {snapshot.final_decision ?? "—"}
                  </dd>
                </div>
              </dl>

              {/* Risk gauge inline */}
              {trustValue !== null && Number.isFinite(trustValue) && (
                <div className="mt-6 pt-6 border-t border-[#333] flex justify-center print:hidden">
                  <RiskGauge
                    value={trustValue}
                    label="TRUST SCORE"
                    size={140}
                    strokeWidth={10}
                  />
                </div>
              )}

              {/* Print-only numeric values */}
              <dl className="mt-6 space-y-3 text-sm pt-4 border-t border-[#333] font-mono">
                <div className="flex justify-between">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">TRUST SCORE</dt>
                  <dd className="text-white font-bold print:text-black">
                    {trustValue !== null && Number.isFinite(trustValue) ? trustValue.toFixed(4) : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 uppercase tracking-widest text-xs">RISK VALUE</dt>
                  <dd className="text-white font-bold print:text-black">
                    {riskValue !== null && Number.isFinite(riskValue) ? riskValue.toFixed(4) : "—"}
                  </dd>
                </div>
              </dl>
            </div>
          </div>

          {/* Chain Reference */}
          {snapshot.trust_score_id && (
            <div data-reveal className="w-full">
              <div className="p-6 border border-[#333] bg-black print:border-black print:bg-white hover:border-[#FF00FF] transition-colors duration-300">
                <h2 className="font-sans font-bold uppercase tracking-widest text-[#FF00FF] mb-4 print:text-black">CHAIN REFERENCE HASHES</h2>
                <div className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <dl className="space-y-4 text-sm font-mono">
                    <div className="flex justify-between pb-2 border-b border-[#333] print:border-gray-300">
                      <dt className="text-gray-500 uppercase tracking-widest text-xs">TRUST SCORE ID</dt>
                      <dd><HashDisplay hash={snapshot.trust_score_id} /></dd>
                    </div>
                    {snapshot.risk_score_id && (
                      <div className="flex justify-between pb-2 border-b border-[#333] print:border-gray-300">
                        <dt className="text-gray-500 uppercase tracking-widest text-xs">RISK SCORE ID</dt>
                        <dd><HashDisplay hash={snapshot.risk_score_id} /></dd>
                      </div>
                    )}
                  </dl>
                  <dl className="space-y-4 text-sm font-mono">
                    {snapshot.policy_decision_id && (
                      <div className="flex justify-between pb-2 border-b border-[#333] print:border-gray-300">
                        <dt className="text-gray-500 uppercase tracking-widest text-xs">POLICY DECISION ID</dt>
                        <dd><HashDisplay hash={snapshot.policy_decision_id} /></dd>
                      </div>
                    )}
                    {snapshot.crypto_profile_id && (
                      <div className="flex justify-between pb-2 border-b border-[#333] print:border-gray-300">
                        <dt className="text-gray-500 uppercase tracking-widest text-xs">CRYPTO PROFILE ID</dt>
                        <dd><HashDisplay hash={snapshot.crypto_profile_id} /></dd>
                      </div>
                    )}
                  </dl>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
