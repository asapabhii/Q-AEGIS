"use client";

import { useEffect, useState } from "react";
import { FileText, Printer, Trash2 } from "lucide-react";

import Badge from "@/components/ui/Badge";
import HashDisplay from "@/components/ui/HashDisplay";
import RiskGauge from "@/components/ui/RiskGauge";
import NotPermitted from "@/components/ui/NotPermitted";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import {
  getDocument,
  shredDocument,
  downloadDocumentSummary,
  ApiError,
} from "@/lib/api/client";
import type {
  DocumentSnapshot,
  SensitivityLabel,
} from "@/lib/api/types";
import { cryptoLabel, cryptoTone } from "@/lib/crypto-labels";

const LABEL_TONES: Record<
  SensitivityLabel,
  "public" | "internal" | "confidential" | "restricted"
> = {
  PUBLIC: "public",
  INTERNAL: "internal",
  CONFIDENTIAL: "confidential",
  RESTRICTED: "restricted",
};

// The report reads the document snapshot, which the backend gates behind the
// inventory role set. Send the caller's REAL role and render an honest 403
// rather than clamping anyone to security_admin.
const VIEW_ALLOWED = ACCESS.inventory;

export default function DocumentSummaryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const { role } = useRole();
  const permitted = roleAllowed(VIEW_ALLOWED, role);
  const canExport = roleAllowed(ACCESS.export, role);
  const canShred = roleAllowed(ACCESS.shred, role);
  const [documentId, setDocumentId] = useState<string>("");

  useEffect(() => {
    params.then((p) => setDocumentId(p.id));
  }, [params]);

  const [snapshot, setSnapshot] = useState<DocumentSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [shredConfirming, setShredConfirming] = useState(false);
  const [shredLoading, setShredLoading] = useState(false);
  const [shredError, setShredError] = useState<string | null>(null);

  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = async () => {
    if (!documentId) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadDocumentSummary(documentId, "pdf", role);
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setDownloading(false);
    }
  };

  const handleShred = async () => {
    if (!shredConfirming) {
      setShredConfirming(true);
      return;
    }

    setShredLoading(true);
    setShredError(null);
    try {
      await shredDocument({ document_id: documentId, confirmed: true }, role);
      // Reload snapshot to reflect archived status
      const doc = await getDocument(documentId, role);
      setSnapshot(doc);
    } catch (err) {
      setShredError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setShredLoading(false);
      setShredConfirming(false);
    }
  };

  useEffect(() => {
    if (!documentId || !permitted) {
      return;
    }
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
  }, [documentId, role, permitted]);

  const riskValue =
    snapshot?.risk_value !== null && snapshot?.risk_value !== undefined
      ? Number(snapshot.risk_value)
      : null;
  const trustValue =
    snapshot?.trust_score !== null && snapshot?.trust_score !== undefined
      ? Number(snapshot.trust_score)
      : null;

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-4xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={VIEW_ALLOWED}
          resource="The document summary report"
        />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="mx-auto w-full max-w-4xl space-y-6 px-6 py-8 rounded-none print:py-0 print:px-0 print:space-y-4 print:bg-white print:text-black"
      style={{ color: "var(--color-text-primary)" }}
    >
      {/* Page Header */}
      <div
        data-reveal
        className="flex flex-col sm:flex-row items-start justify-between gap-4 mb-6 pb-4 print:mb-2 print:border-black"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-lg print:hidden"
            style={{
              backgroundColor: "var(--color-bg-tertiary)",
              border: "1px solid var(--color-accent)",
            }}
          >
            <FileText
              className="h-6 w-6"
              style={{ color: "var(--color-accent)" }}
            />
          </div>
          <div>
            <h1
              className="font-semibold print:text-black print:text-xl"
              style={{
                fontSize: "var(--font-size-xl)",
                color: "var(--color-text-primary)",
              }}
            >
              Document Summary Report
            </h1>
            <p
              className="mono-data text-xs mt-1 print:text-gray-700"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              {documentId}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 print:hidden">
          {canShred &&
            snapshot &&
            snapshot.current_status !== "archived" && (
              <button
                type="button"
                onClick={handleShred}
                disabled={shredLoading}
                onMouseLeave={() => setShredConfirming(false)}
                className="btn"
                style={{
                  borderColor: "var(--status-fail)",
                  color: shredConfirming ? "#fff" : "var(--status-fail)",
                  backgroundColor: shredConfirming
                    ? "var(--status-fail)"
                    : "transparent",
                }}
              >
                <Trash2 className="h-4 w-4" />
                {shredLoading
                  ? "Shredding…"
                  : shredConfirming
                    ? "Confirm irreversible shred"
                    : "Shred encryption key"}
              </button>
            )}
          {canExport && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="btn btn-secondary"
            >
              <Printer className="h-4 w-4" />
              {downloading ? "Downloading…" : "Download PDF"}
            </button>
          )}
        </div>
      </div>

      {loading && (
        <p
          className="text-sm animate-pulse"
          style={{ color: "var(--color-accent)" }}
        >
          Fetching document snapshot…
        </p>
      )}

      {error && (
        <p className="text-sm" style={{ color: "var(--status-fail)" }}>
          {error}
        </p>
      )}

      {shredError && (
        <p className="text-sm mb-4" style={{ color: "var(--status-fail)" }}>
          {shredError}
        </p>
      )}

      {downloadError && (
        <p className="text-sm mb-4" style={{ color: "var(--status-fail)" }}>
          {downloadError}
        </p>
      )}

      {!loading && !error && snapshot && (
        <>
          <div
            data-reveal
            className="grid gap-6 md:grid-cols-2 print:gap-4 print:grid-cols-1"
          >
            {/* Classification Card */}
            <div className="card p-6 print:border-black print:bg-white">
              <h2
                className="font-semibold uppercase tracking-widest mb-4 print:text-black"
                style={{
                  fontSize: "var(--font-size-sm)",
                  color: "var(--status-pass)",
                }}
              >
                Classification
              </h2>
              <dl className="space-y-4 text-sm mono-data">
                <div
                  className="flex items-center justify-between pb-3"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Label
                  </dt>
                  <dd>
                    {snapshot.sensitivity_label ? (
                      <Badge
                        label={snapshot.sensitivity_label}
                        tone={LABEL_TONES[snapshot.sensitivity_label]}
                      />
                    ) : (
                      <span style={{ color: "var(--color-text-tertiary)" }}>—</span>
                    )}
                  </dd>
                </div>
                <div
                  className="flex justify-between pb-3"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Source
                  </dt>
                  <dd
                    className="font-semibold print:text-black"
                    style={{ color: "var(--status-pass)" }}
                  >
                    {snapshot.label_source ?? "—"}
                  </dd>
                </div>
                <div className="flex justify-between pb-1">
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Override ID
                  </dt>
                  <dd>
                    {snapshot.override_id ? (
                      <HashDisplay hash={snapshot.override_id} />
                    ) : (
                      <span style={{ color: "var(--color-text-tertiary)" }}>—</span>
                    )}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Protection Profile Card */}
            <div className="card p-6 print:border-black print:bg-white">
              <h2
                className="font-semibold uppercase tracking-widest mb-4 print:text-black"
                style={{
                  fontSize: "var(--font-size-sm)",
                  color: "var(--crypto-pqc)",
                }}
              >
                Protection Profile
              </h2>
              <dl className="space-y-4 text-sm mono-data">
                <div
                  className="flex items-center justify-between pb-3"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Profile
                  </dt>
                  <dd>
                    {snapshot.profile_type ? (
                      <Badge
                        label={cryptoLabel(snapshot.profile_type, "full")}
                        tone={cryptoTone(snapshot.profile_type)}
                      />
                    ) : (
                      <span style={{ color: "var(--color-text-tertiary)" }}>—</span>
                    )}
                  </dd>
                </div>
                <div className="flex justify-between pb-3">
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Decision
                  </dt>
                  <dd
                    className="font-semibold uppercase print:text-black"
                    style={{ color: "var(--crypto-pqc)" }}
                  >
                    {snapshot.final_decision ?? "—"}
                  </dd>
                </div>
              </dl>

              {/* Risk gauge inline */}
              {trustValue !== null && Number.isFinite(trustValue) && (
                <div
                  className="mt-6 pt-6 flex justify-center print:hidden"
                  style={{ borderTop: "1px solid var(--color-border)" }}
                >
                  <RiskGauge
                    value={trustValue}
                    label="TRUST SCORE"
                    size={140}
                    strokeWidth={10}
                  />
                </div>
              )}

              {/* Numeric values */}
              <dl
                className="mt-6 space-y-3 text-sm pt-4 mono-data"
                style={{ borderTop: "1px solid var(--color-border)" }}
              >
                <div className="flex justify-between">
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Trust Score
                  </dt>
                  <dd
                    className="font-semibold print:text-black"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {trustValue !== null && Number.isFinite(trustValue)
                      ? trustValue.toFixed(4)
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="uppercase tracking-widest text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Risk Value
                  </dt>
                  <dd
                    className="font-semibold print:text-black"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {riskValue !== null && Number.isFinite(riskValue)
                      ? riskValue.toFixed(4)
                      : "—"}
                  </dd>
                </div>
              </dl>
            </div>
          </div>

          {/* Chain Reference */}
          {snapshot.trust_score_id && (
            <div data-reveal className="w-full">
              <div className="card p-6 print:border-black print:bg-white">
                <h2
                  className="font-semibold uppercase tracking-widest mb-4 print:text-black"
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-accent)",
                  }}
                >
                  Chain Reference Hashes
                </h2>
                <div className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
                  <dl className="space-y-4 text-sm mono-data">
                    <div
                      className="flex justify-between pb-2"
                      style={{ borderBottom: "1px solid var(--color-border)" }}
                    >
                      <dt
                        className="uppercase tracking-widest text-xs"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        Trust Score ID
                      </dt>
                      <dd>
                        <HashDisplay hash={snapshot.trust_score_id} />
                      </dd>
                    </div>
                    {snapshot.risk_score_id && (
                      <div
                        className="flex justify-between pb-2"
                        style={{ borderBottom: "1px solid var(--color-border)" }}
                      >
                        <dt
                          className="uppercase tracking-widest text-xs"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          Risk Score ID
                        </dt>
                        <dd>
                          <HashDisplay hash={snapshot.risk_score_id} />
                        </dd>
                      </div>
                    )}
                  </dl>
                  <dl className="space-y-4 text-sm mono-data">
                    {snapshot.policy_decision_id && (
                      <div
                        className="flex justify-between pb-2"
                        style={{ borderBottom: "1px solid var(--color-border)" }}
                      >
                        <dt
                          className="uppercase tracking-widest text-xs"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          Policy Decision ID
                        </dt>
                        <dd>
                          <HashDisplay hash={snapshot.policy_decision_id} />
                        </dd>
                      </div>
                    )}
                    {snapshot.crypto_profile_id && (
                      <div
                        className="flex justify-between pb-2"
                        style={{ borderBottom: "1px solid var(--color-border)" }}
                      >
                        <dt
                          className="uppercase tracking-widest text-xs"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          Crypto Profile ID
                        </dt>
                        <dd>
                          <HashDisplay hash={snapshot.crypto_profile_id} />
                        </dd>
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
