"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

import Badge from "@/components/ui/Badge";
import DataTable from "@/components/ui/DataTable";
import { listDocuments, ApiError } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import type {
  CryptoProfileType,
  DocumentSnapshot,
  SensitivityLabel,
} from "@/lib/api/types";

const HIGH_RISK_THRESHOLD = 0.5;

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
  hybrid: "Hybrid",
  post_quantum: "PQC",
};

function parseRisk(value: string | null): number | null {
  if (value === null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatScore(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export default function RiskDashboardPage() {
  const { role } = useRole();
  const [documents, setDocuments] = useState<DocumentSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDocuments(role)
      .then((res) => {
        if (cancelled) return;
        setDocuments(res.documents);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setDocuments([]);
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role]);

  const riskValues = documents
    .map((d) => parseRisk(d.risk_value))
    .filter((v): v is number => v !== null);

  const totalDocuments = documents.length;
  const averageRisk =
    riskValues.length > 0
      ? riskValues.reduce((sum, v) => sum + v, 0) / riskValues.length
      : 0;
  const activeOverrides = documents.filter(
    (d) => d.final_decision !== null && d.final_decision !== "allow"
  ).length;

  const highRiskCount = riskValues.filter((r) => r >= HIGH_RISK_THRESHOLD)
    .length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Loading security data...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <div className="card p-6" style={{ borderColor: "var(--status-fail)" }}>
          <div className="flex items-center gap-3">
            <AlertTriangle
              className="h-5 w-5"
              style={{ color: "var(--status-fail)" }}
            />
            <p className="text-sm" style={{ color: "var(--status-fail)" }}>
              {error}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // High risk documents for table
  const highRiskRows = documents
    .filter((d) => {
      const risk = parseRisk(d.risk_value);
      return risk !== null && risk >= HIGH_RISK_THRESHOLD;
    })
    .slice(0, 20)
    .map((doc) => {
      const risk = parseRisk(doc.risk_value);
      const trust = doc.trust_score !== null ? Number(doc.trust_score) : null;
      return {
        document: doc.filename,
        label: doc.sensitivity_label ? (
          <Badge
            label={doc.sensitivity_label}
            tone={LABEL_TONES[doc.sensitivity_label]}
            size="sm"
          />
        ) : (
          <span style={{ color: "var(--color-text-tertiary)" }}>-</span>
        ),
        risk:
          risk !== null ? (
            <span
              style={{
                color:
                  risk >= 0.7
                    ? "var(--status-fail)"
                    : risk >= 0.5
                      ? "var(--status-override)"
                      : "var(--status-pass)",
              }}
            >
              {formatScore(risk)}
            </span>
          ) : (
            <span style={{ color: "var(--color-text-tertiary)" }}>-</span>
          ),
        trust:
          trust !== null && Number.isFinite(trust) ? (
            formatScore(trust, 1)
          ) : (
            <span style={{ color: "var(--color-text-tertiary)" }}>-</span>
          ),
        profile: doc.profile_type ? (
          <Badge
            label={PROFILE_LABELS[doc.profile_type]}
            tone={PROFILE_TONES[doc.profile_type]}
            size="sm"
          />
        ) : (
          <span style={{ color: "var(--color-text-tertiary)" }}>-</span>
        ),
      };
    });

  return (
    <div className="mx-auto w-full max-w-screen-xl px-6 py-8 space-y-8">
      {/* Page Header */}
      <header>
        <h1
          className="font-semibold mb-1"
          style={{
            fontSize: "var(--font-size-2xl)",
            color: "var(--color-text-primary)",
          }}
        >
          Security Dashboard
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Real-time document classification and risk assessment status
        </p>
      </header>

      {/* Metrics Grid */}
      <section>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Total Documents */}
          <div className="card card-hover p-4">
            <div className="flex items-start justify-between mb-2">
              <FileText
                className="h-4 w-4"
                style={{ color: "var(--color-text-tertiary)" }}
              />
              <span
                className="mono-data text-2xl font-semibold"
                style={{ color: "var(--color-text-primary)" }}
              >
                {totalDocuments}
              </span>
            </div>
            <div
              className="text-xs uppercase tracking-wider mb-1"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Total Documents
            </div>
            <div
              className="text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Registered in inventory
            </div>
          </div>

          {/* High Risk */}
          <div className="card card-hover p-4">
            <div className="flex items-start justify-between mb-2">
              <AlertTriangle
                className="h-4 w-4"
                style={{
                  color:
                    highRiskCount >= 10
                      ? "var(--status-fail)"
                      : highRiskCount >= 5
                        ? "var(--status-override)"
                        : "var(--color-text-tertiary)",
                }}
              />
              <span
                className="mono-data text-2xl font-semibold"
                style={{
                  color:
                    highRiskCount >= 10
                      ? "var(--status-fail)"
                      : highRiskCount >= 5
                        ? "var(--status-override)"
                        : "var(--color-text-primary)",
                }}
              >
                {highRiskCount}
              </span>
            </div>
            <div
              className="text-xs uppercase tracking-wider mb-1"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              High Risk
            </div>
            <div
              className="flex items-center gap-1.5 text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {highRiskCount > 0 ? (
                <>
                  <TrendingDown className="h-3 w-3" />
                  <span>3 resolved</span>
                </>
              ) : (
                <span>No active alerts</span>
              )}
            </div>
          </div>

          {/* Average Risk */}
          <div className="card card-hover p-4">
            <div className="flex items-start justify-between mb-2">
              <TrendingUp
                className="h-4 w-4"
                style={{ color: "var(--color-text-tertiary)" }}
              />
              <span
                className="mono-data text-2xl font-semibold"
                style={{
                  color:
                    averageRisk >= 0.7
                      ? "var(--status-fail)"
                      : averageRisk >= 0.5
                        ? "var(--status-override)"
                        : "var(--color-text-primary)",
                }}
              >
                {formatScore(averageRisk)}
              </span>
            </div>
            <div
              className="text-xs uppercase tracking-wider mb-1"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Avg Risk Score
            </div>
            <div
              className="text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Mean across {riskValues.length} assessments
            </div>
          </div>

          {/* Policy Overrides */}
          <div className="card card-hover p-4">
            <div className="flex items-start justify-between mb-2">
              <ShieldCheck
                className="h-4 w-4"
                style={{ color: "var(--color-text-tertiary)" }}
              />
              <span
                className="mono-data text-2xl font-semibold"
                style={{ color: "var(--color-text-primary)" }}
              >
                {activeOverrides}
              </span>
            </div>
            <div
              className="text-xs uppercase tracking-wider mb-1"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Policy Overrides
            </div>
            <div
              className="text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              AI decisions overridden
            </div>
          </div>
        </div>
      </section>

      {/* High Risk Documents Table */}
      <section>
        <div className="card p-6">
          <header className="mb-6">
            <h2
              className="font-semibold mb-1"
              style={{
                fontSize: "var(--font-size-lg)",
                color: "var(--color-text-primary)",
              }}
            >
              High-Risk Documents
            </h2>
            <p
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-secondary)",
              }}
            >
              Documents at or above risk threshold ({formatScore(
                HIGH_RISK_THRESHOLD
              )})
            </p>
          </header>

          <DataTable
            label="High-risk documents"
            columns={[
              { key: "document", header: "Document" },
              { key: "label", header: "Label" },
              {
                key: "risk",
                header: "Risk",
                align: "right",
                mono: true,
              },
              {
                key: "trust",
                header: "Trust",
                align: "right",
                mono: true,
              },
              { key: "profile", header: "Protection" },
            ]}
            rows={highRiskRows}
            emptyMessage="No documents currently exceed the high-risk threshold."
          />
        </div>
      </section>

      {/* Distribution Summary */}
      <section>
        <div className="grid gap-4 md:grid-cols-2">
          {/* Sensitivity Distribution */}
          <div className="card p-6">
            <h3
              className="font-semibold mb-4"
              style={{
                fontSize: "var(--font-size-base)",
                color: "var(--color-text-primary)",
              }}
            >
              Sensitivity Distribution
            </h3>
            <div className="space-y-3">
              {(
                ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"] as const
              ).map((label) => {
                const count = documents.filter(
                  (d) => d.sensitivity_label === label
                ).length;
                const percentage =
                  totalDocuments > 0 ? (count / totalDocuments) * 100 : 0;
                return (
                  <div key={label}>
                    <div className="flex items-center justify-between mb-1.5">
                      <Badge
                        label={label}
                        tone={LABEL_TONES[label]}
                        size="sm"
                      />
                      <span
                        className="mono-data text-xs"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {count} ({percentage.toFixed(0)}%)
                      </span>
                    </div>
                    <div
                      className="h-1.5 rounded-full overflow-hidden"
                      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                    >
                      <div
                        className="h-full transition-all duration-500"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor:
                            label === "PUBLIC"
                              ? "var(--status-pass)"
                              : label === "INTERNAL"
                                ? "var(--status-info)"
                                : label === "CONFIDENTIAL"
                                  ? "var(--status-override)"
                                  : "var(--status-fail)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Crypto Profile Distribution */}
          <div className="card p-6">
            <h3
              className="font-semibold mb-4"
              style={{
                fontSize: "var(--font-size-base)",
                color: "var(--color-text-primary)",
              }}
            >
              Protection Profiles
            </h3>
            <div className="space-y-3">
              {(
                ["aes256", "hybrid", "post_quantum"] as CryptoProfileType[]
              ).map((profile) => {
                const count = documents.filter(
                  (d) => d.profile_type === profile
                ).length;
                const percentage =
                  totalDocuments > 0 ? (count / totalDocuments) * 100 : 0;
                return (
                  <div key={profile}>
                    <div className="flex items-center justify-between mb-1.5">
                      <Badge
                        label={PROFILE_LABELS[profile]}
                        tone={PROFILE_TONES[profile]}
                        size="sm"
                      />
                      <span
                        className="mono-data text-xs"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {count} ({percentage.toFixed(0)}%)
                      </span>
                    </div>
                    <div
                      className="h-1.5 rounded-full overflow-hidden"
                      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                    >
                      <div
                        className="h-full transition-all duration-500"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor:
                            profile === "aes256"
                              ? "var(--crypto-aes)"
                              : profile === "hybrid"
                                ? "var(--crypto-hybrid)"
                                : "var(--crypto-pqc)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
