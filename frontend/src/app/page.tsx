"use client";

import { useState, useCallback } from "react";
import {
  checkHealth,
  registerAndClassify,
  ApiError,
} from "@/lib/api/client";
import type {
  HealthResponse,
  ClassificationResponse,
  DocumentResponse,
  UserRole,
  SensitivityLabel,
} from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Sensitivity label badge colours
// ---------------------------------------------------------------------------

const LABEL_STYLES: Record<SensitivityLabel, string> = {
  PUBLIC:
    "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  INTERNAL:
    "bg-blue-500/15 text-blue-400 border-blue-500/30",
  CONFIDENTIAL:
    "bg-amber-500/15 text-amber-400 border-amber-500/30",
  RESTRICTED:
    "bg-red-500/15 text-red-400 border-red-500/30",
};

function LabelBadge({ label }: { label: SensitivityLabel }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${LABEL_STYLES[label]}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Role descriptions — authorization plumbing, NOT authentication
// ---------------------------------------------------------------------------

const AVAILABLE_ROLES: { value: UserRole; label: string }[] = [
  { value: "data_owner", label: "Data Owner" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "security_admin", label: "Security Admin" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  // Health
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Classify flow
  const [role, setRole] = useState<UserRole>("data_owner");
  const [filename, setFilename] = useState("quarterly-report.pdf");
  const [content, setContent] = useState(
    "This document contains confidential financial projections and restricted trade secrets."
  );
  const [registeredDocument, setRegisteredDocument] =
    useState<DocumentResponse | null>(null);
  const [classification, setClassification] =
    useState<ClassificationResponse | null>(null);
  const [classifyError, setClassifyError] = useState<string | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);

  // ------ Health check ------
  const handleHealthCheck = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const res = await checkHealth();
      setHealth(res);
    } catch (err) {
      setHealthError(
        err instanceof ApiError ? err.message : "Network error"
      );
    } finally {
      setHealthLoading(false);
    }
  }, []);

  // ------ Register + Classify ------
  const handleClassify = useCallback(async () => {
    setClassifyLoading(true);
    setClassifyError(null);
    setRegisteredDocument(null);
    setClassification(null);
    try {
      const { document: doc, classification: cls } =
        await registerAndClassify(filename, content, role);
      setRegisteredDocument(doc);
      setClassification(cls);
    } catch (err) {
      setClassifyError(
        err instanceof ApiError ? err.message : "Network error"
      );
    } finally {
      setClassifyLoading(false);
    }
  }, [filename, content, role]);

  return (
    <div className="flex-1 flex flex-col">
      {/* ── Header ────────────────────────────────────────── */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold">
              Q
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Q-AEGIS Shield
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                Quantum-Adaptive Encryption Governance
              </p>
            </div>
          </div>

          {/* Health status dot */}
          <div className="flex items-center gap-2 text-sm">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                health
                  ? "bg-emerald-400 animate-pulse-glow text-emerald-400"
                  : "bg-slate-600"
              }`}
            />
            <span className="text-[var(--color-text-secondary)]">
              {health ? `v${health.version}` : "Not checked"}
            </span>
          </div>
        </div>
      </header>

      {/* ── Main ──────────────────────────────────────────── */}
      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-8">
        {/* ── Health Card ─────────────────────────────────── */}
        <section
          id="health-section"
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 card-shimmer"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold">System Health</h2>
            <button
              id="health-check-btn"
              onClick={handleHealthCheck}
              disabled={healthLoading}
              className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {healthLoading ? "Checking…" : "Check Health"}
            </button>
          </div>

          {healthError && (
            <p className="text-sm text-red-400">{healthError}</p>
          )}

          {health && (
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-[var(--color-text-muted)] block text-xs uppercase tracking-wider mb-1">
                  Status
                </span>
                <span className="text-emerald-400 font-medium">
                  {health.status}
                </span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)] block text-xs uppercase tracking-wider mb-1">
                  Service
                </span>
                <span className="font-medium">{health.service}</span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)] block text-xs uppercase tracking-wider mb-1">
                  Version
                </span>
                <span className="font-medium">{health.version}</span>
              </div>
            </div>
          )}
        </section>

        {/* ── Classification Workbench ────────────────────── */}
        <section
          id="classify-section"
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 card-shimmer"
        >
          <h2 className="text-base font-semibold mb-1">
            Document Classification
          </h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Register a document then classify its sensitivity. Two API calls,
            not one — <code className="text-xs">document_id</code> is a real
            foreign key.
          </p>

          <div className="grid gap-5 md:grid-cols-2">
            {/* Left: inputs */}
            <div className="space-y-4">
              {/* Role selector */}
              <div>
                <label
                  htmlFor="role-select"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Caller Role
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    (authorization plumbing, not authentication)
                  </span>
                </label>
                <select
                  id="role-select"
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                >
                  {AVAILABLE_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Filename */}
              <div>
                <label
                  htmlFor="filename-input"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Filename
                </label>
                <input
                  id="filename-input"
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                  placeholder="e.g. quarterly-report.pdf"
                />
              </div>

              {/* Content */}
              <div>
                <label
                  htmlFor="content-input"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Document Content
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    (Phase 1: inline text, not file upload)
                  </span>
                </label>
                <textarea
                  id="content-input"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none resize-y"
                  placeholder="Paste document text to classify…"
                />
              </div>

              <button
                id="classify-btn"
                onClick={handleClassify}
                disabled={
                  classifyLoading || !filename.trim() || !content.trim()
                }
                className="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {classifyLoading
                  ? "Classifying…"
                  : "Register & Classify"}
              </button>

              {classifyError && (
                <p className="text-sm text-red-400">{classifyError}</p>
              )}
            </div>

            {/* Right: results */}
            <div className="space-y-4">
              {registeredDocument && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Step 1 — Document Registered
                  </h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        ID
                      </dt>
                      <dd className="font-mono text-xs">
                        {registeredDocument.id}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Filename
                      </dt>
                      <dd>{registeredDocument.filename}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Status
                      </dt>
                      <dd className="text-cyan-400 font-medium">
                        {registeredDocument.current_status}
                      </dd>
                    </div>
                  </dl>
                </div>
              )}

              {classification && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Step 2 — Classification Result
                  </h3>
                  <dl className="space-y-3 text-sm">
                    <div className="flex justify-between items-center">
                      <dt className="text-[var(--color-text-secondary)]">
                        Sensitivity
                      </dt>
                      <dd>
                        <LabelBadge
                          label={classification.sensitivity_label}
                        />
                      </dd>
                    </div>

                    {classification.is_defaulted && (
                      <div className="flex justify-between items-center">
                        <dt className="text-[var(--color-text-secondary)]">
                          Escalated from
                        </dt>
                        <dd className="flex items-center gap-2">
                          <LabelBadge
                            label={classification.base_label}
                          />
                          <span className="text-amber-400 text-xs">
                            ⚠ fail-safe
                          </span>
                        </dd>
                      </div>
                    )}

                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Confidence
                      </dt>
                      <dd className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
                            style={{
                              width: `${classification.confidence * 100}%`,
                            }}
                          />
                        </div>
                        <span className="font-mono text-xs">
                          {(classification.confidence * 100).toFixed(1)}%
                        </span>
                      </dd>
                    </div>

                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Threshold
                      </dt>
                      <dd className="font-mono text-xs">
                        {(
                          classification.confidence_threshold * 100
                        ).toFixed(0)}
                        %
                      </dd>
                    </div>

                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Model
                      </dt>
                      <dd className="font-mono text-xs">
                        {classification.model_version}
                      </dd>
                    </div>

                    {classification.matched_keywords.length > 0 && (
                      <div>
                        <dt className="text-[var(--color-text-secondary)] mb-1">
                          Matched Keywords
                        </dt>
                        <dd className="flex flex-wrap gap-1.5">
                          {classification.matched_keywords.map((kw) => (
                            <span
                              key={kw}
                              className="inline-flex rounded-md bg-slate-700/60 px-2 py-0.5 text-xs font-mono"
                            >
                              {kw}
                            </span>
                          ))}
                        </dd>
                      </div>
                    )}

                    <div>
                      <dt className="text-[var(--color-text-secondary)] mb-1">
                        Rationale
                      </dt>
                      <dd className="text-xs text-[var(--color-text-muted)] leading-relaxed">
                        {classification.rationale}
                      </dd>
                    </div>
                  </dl>
                </div>
              )}

              {!registeredDocument && !classification && !classifyError && (
                <div className="flex items-center justify-center h-48 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Results will appear here
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* ── Footer ────────────────────────────────────────── */}
      <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>Q-AEGIS Shield · SPEC.md 3.13</span>
          <span>
            Authorization stub — server decides, UI reflects
          </span>
        </div>
      </footer>
    </div>
  );
}
