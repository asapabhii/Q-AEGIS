"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { LabelBadge } from "@/components/LabelBadge";
import {
  checkHealth,
  registerAndClassify,
  registerUploadAndClassify,
  runAssessment,
  ApiError,
} from "@/lib/api/client";
import type {
  HealthResponse,
  ClassificationResponse,
  DocumentResponse,
  AssessmentResponse,
  UserRole,
} from "@/lib/api/types";
import {
  getAccessToken,
  getSessionUser,
  setDevRole,
} from "@/lib/auth/session";

const AVAILABLE_ROLES: { value: UserRole; label: string }[] = [
  { value: "data_owner", label: "Data Owner" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "security_admin", label: "Security Admin" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

/** Client-side mirror of ``UPLOAD_MAX_BYTES`` (50 MiB). */
const UPLOAD_MAX_BYTES = 50 * 1024 * 1024;

export default function ClassifyPage() {
  const session = typeof window !== "undefined" ? getSessionUser() : null;
  const hasJwt = typeof window !== "undefined" && Boolean(getAccessToken());

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const [role, setRole] = useState<UserRole>(session?.role ?? "data_owner");
  const [filename, setFilename] = useState("quarterly-report.pdf");
  const [content, setContent] = useState(
    "This document contains confidential financial projections and restricted trade secrets."
  );
  const [file, setFile] = useState<File | null>(null);
  const [registeredDocument, setRegisteredDocument] =
    useState<DocumentResponse | null>(null);
  const [classification, setClassification] =
    useState<ClassificationResponse | null>(null);
  const [classifyError, setClassifyError] = useState<string | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [assessError, setAssessError] = useState<string | null>(null);
  const [assessLoading, setAssessLoading] = useState(false);

  useEffect(() => {
    if (!hasJwt) setDevRole(role);
  }, [role, hasJwt]);

  const handleHealthCheck = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      setHealth(await checkHealth());
    } catch (err) {
      setHealthError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const handleClassify = useCallback(async () => {
    setClassifyLoading(true);
    setClassifyError(null);
    setRegisteredDocument(null);
    setClassification(null);
    setAssessment(null);
    setAssessError(null);
    try {
      if (file) {
        const result = await registerUploadAndClassify(file, content, role);
        setRegisteredDocument(result.document);
        setClassification(result.classification);
        if (result.upload.extracted_text) {
          setContent(result.upload.extracted_text);
        }
      } else {
        const { document: doc, classification: cls } = await registerAndClassify(
          filename,
          content,
          role
        );
        setRegisteredDocument(doc);
        setClassification(cls);
      }
    } catch (err) {
      setClassifyError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setClassifyLoading(false);
    }
  }, [filename, content, role, file]);

  const effectiveRole = session?.role ?? role;
  const canAssess =
    effectiveRole === "security_analyst" || effectiveRole === "security_admin";

  const handleAssess = useCallback(async () => {
    if (!registeredDocument || !canAssess) return;
    setAssessLoading(true);
    setAssessError(null);
    setAssessment(null);
    try {
      setAssessment(
        await runAssessment(
          {
            document_id: registeredDocument.id,
            device_id: "workstation-01",
            device_is_new: false,
            accessed_at: new Date().toISOString(),
            after_hours: false,
            content,
          },
          role
        )
      );
    } catch (err) {
      setAssessError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setAssessLoading(false);
    }
  }, [registeredDocument, role, content, canAssess]);

  const canClassify = file
    ? !classifyLoading && file.size <= UPLOAD_MAX_BYTES
    : !classifyLoading && Boolean(filename.trim()) && Boolean(content.trim());

  return (
    <AppShell
      active="/"
      eyebrow="Classify / assess / protect"
      title="Operator workbench"
      summary="Register a document, classify sensitivity, run the full trust and policy path, then jump directly into override, agent, or audit workflows."
      status={health ? `v${health.version}` : "Backend not checked"}
    >
      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.65fr]">
        <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-panel)] p-5 shadow-[var(--shadow-panel)]">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">System Health</h2>
            <button
              id="health-check-btn"
              onClick={handleHealthCheck}
              disabled={healthLoading}
              className="bg-[var(--color-accent-cyan)] px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {healthLoading ? "Checking..." : "Check Health"}
            </button>
          </div>
          {healthError && <p className="text-sm text-red-400">{healthError}</p>}
          {health && (
            <div className="grid gap-4 text-sm sm:grid-cols-3 xl:grid-cols-1">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-3">
                <span className="text-[var(--color-text-muted)] block text-xs mb-1">
                  Status
                </span>
                <span className="text-emerald-400 font-medium">{health.status}</span>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-3">
                <span className="text-[var(--color-text-muted)] block text-xs mb-1">
                  Service
                </span>
                <span className="font-medium">{health.service}</span>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-3">
                <span className="text-[var(--color-text-muted)] block text-xs mb-1">
                  Version
                </span>
                <span className="font-medium">{health.version}</span>
              </div>
            </div>
          )}
        </section>

        <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-panel)] p-5 shadow-[var(--shadow-panel)]">
          <h2 className="text-base font-semibold mb-1">Document Classification</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Upload a file (50 MB max) or paste text. Prefer{" "}
            <Link href="/login" className="text-cyan-400 hover:underline">
              JWT login
            </Link>
            ; role selector is DEV-ONLY when no token is stored.
          </p>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              {!hasJwt && (
                <div>
                  <label
                    htmlFor="role-select"
                    className="block text-xs font-medium mb-1.5"
                  >
                    Caller Role
                    <span className="ml-1 text-[var(--color-text-muted)]">
                      (DEV-ONLY bypass when no JWT)
                    </span>
                  </label>
                  <select
                    id="role-select"
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
                  >
                    {AVAILABLE_ROLES.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {hasJwt && session && (
                <p className="text-xs text-[var(--color-text-muted)]">
                  Signed in as {session.email} ({session.role})
                </p>
              )}

              <div>
                <label htmlFor="file-input" className="block text-xs font-medium mb-1.5">
                  Upload file
                </label>
                <div className="border-2 border-dashed border-teal-300/40 bg-teal-300/5 px-4 py-4">
                  <input
                    id="file-input"
                    type="file"
                    accept=".pdf,.txt,.md,.csv,.json,.doc,.docx,.png,.jpg,.jpeg,.webp"
                    onChange={(e) => {
                      const next = e.target.files?.[0] ?? null;
                      if (next && next.size > UPLOAD_MAX_BYTES) {
                        setFile(null);
                        setClassifyError(
                          `File exceeds the ${UPLOAD_MAX_BYTES} byte (50 MiB) upload limit.`
                        );
                        e.target.value = "";
                        return;
                      }
                      setClassifyError(null);
                      setFile(next);
                      if (next) setFilename(next.name);
                    }}
                    className="block w-full text-sm text-[var(--color-text-primary)] file:mr-3 file:rounded-md file:border-0 file:bg-teal-300 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-slate-950 hover:file:bg-teal-200"
                  />
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                    {file
                      ? `Selected: ${file.name} (${file.size.toLocaleString()} bytes)`
                      : "Choose a document to store on disk, then classify."}
                  </p>
                </div>
              </div>

              <div>
                <label
                  htmlFor="filename-input"
                  className="block text-xs font-medium mb-1.5"
                >
                  Filename
                </label>
                <input
                  id="filename-input"
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  disabled={Boolean(file)}
                  className="w-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm disabled:opacity-60"
                />
              </div>

              <div>
                <label
                  htmlFor="content-input"
                  className="block text-xs font-medium mb-1.5"
                >
                  Document Content
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    (fallback if upload has no extractable text)
                  </span>
                </label>
                <textarea
                  id="content-input"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={4}
                  className="w-full resize-y border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
                />
              </div>

              <button
                id="classify-btn"
                onClick={handleClassify}
                disabled={!canClassify}
                className="w-full bg-[var(--color-accent-cyan)] px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                {classifyLoading
                  ? "Classifying..."
                  : file
                    ? "Upload, Register & Classify"
                    : "Register & Classify"}
              </button>
              {classifyError && (
                <p className="text-sm text-red-400">{classifyError}</p>
              )}
            </div>

            <div className="space-y-4">
              {registeredDocument && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 text-sm space-y-2">
                  <p className="text-xs uppercase text-[var(--color-text-muted)]">
                    Document
                  </p>
                  <p className="font-mono text-xs">{registeredDocument.id}</p>
                  <p>
                    {registeredDocument.filename} ·{" "}
                    <span className="text-cyan-400">
                      {registeredDocument.current_status}
                    </span>
                  </p>
                </div>
              )}
              {classification && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 space-y-3">
                  <div className="flex justify-between items-center text-sm">
                    <span>Sensitivity</span>
                    <LabelBadge label={classification.sensitivity_label} />
                  </div>
                  {classification.is_defaulted && (
                    <div className="flex justify-between items-center text-sm">
                      <span>Escalated from</span>
                      <span className="flex items-center gap-2">
                        <LabelBadge label={classification.base_label} />
                        <span className="text-amber-400 text-xs">fail-safe</span>
                      </span>
                    </div>
                  )}
                  <p className="text-xs font-mono">
                    {(classification.confidence * 100).toFixed(1)}%
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {classification.rationale}
                  </p>
                  {registeredDocument && (
                    <div className="space-y-2">
                      <Link
                        href={`/override?document_id=${registeredDocument.id}`}
                        className="text-sm text-cyan-400 hover:underline"
                      >
                        Override this classification
                      </Link>
                      <button
                        type="button"
                        id="assess-btn"
                        onClick={() => void handleAssess()}
                        disabled={assessLoading || !canAssess}
                        className="block w-full border border-[var(--color-border)] px-4 py-2 text-sm hover:bg-[var(--color-bg-card-hover)] disabled:opacity-50"
                      >
                        {assessLoading ? "Running..." : "Run full assessment"}
                      </button>
                      {assessError && (
                        <p className="text-sm text-red-400">{assessError}</p>
                      )}
                      {assessment && (
                        <p className="text-xs font-mono">
                          trust {assessment.consensus_value} ·{" "}
                          {assessment.profile_type} ·{" "}
                          <Link
                            href={`/agents?document_id=${assessment.document_id}`}
                            className="text-cyan-400 hover:underline"
                          >
                            agents
                          </Link>
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
              {!registeredDocument && !classification && !classifyError && (
                <div className="flex h-56 items-center justify-center rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg-card)] text-sm text-[var(--color-text-muted)]">
                  Results will appear here
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
