"use client";

import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  FileText,
  X,
} from "lucide-react";
import Badge from "@/components/ui/Badge";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import {
  ApiError,
  getDocument,
  overrideClassification,
} from "@/lib/api/client";
import type {
  DocumentSnapshot,
  ManualOverrideResponse,
  SensitivityLabel,
} from "@/lib/api/types";
import {
  MIN_JUSTIFICATION_CHARS,
  SENSITIVITY_LABELS,
  canSubmitOverride,
  strippedJustificationLength,
} from "@/lib/override";

const LABEL_TONES: Record<
  string,
  "public" | "internal" | "confidential" | "restricted"
> = {
  PUBLIC: "public",
  INTERNAL: "internal",
  CONFIDENTIAL: "confidential",
  RESTRICTED: "restricted",
};

const LABEL_COLORS: Record<SensitivityLabel, string> = {
  PUBLIC: "#10B981",
  INTERNAL: "#3B82F6",
  CONFIDENTIAL: "#F59E0B",
  RESTRICTED: "#EF4444",
};

export function OverrideScreen({
  initialDocumentId = "",
}: {
  initialDocumentId?: string;
}) {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const { role } = useRole();
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
      setJustification("");
      await loadSnapshot(documentId, { keepResult: true });
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const justChars = strippedJustificationLength(justification);
  const charCountColor =
    justChars >= MIN_JUSTIFICATION_CHARS
      ? "var(--status-pass)"
      : justChars > 0
        ? "var(--status-override)"
        : "var(--color-text-tertiary)";

  return (
    <div
      ref={containerRef}
      className="mx-auto w-full max-w-screen-xl space-y-8 px-6 py-8"
    >
      {/* Hero Header */}
      <header data-reveal className="flex items-start justify-between">
        <div>
          <h1
            className="font-semibold mb-1"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            Security Override Console
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            Manual classification override with permanent audit trail
          </p>
        </div>


      </header>

      {/* Success Banner */}
      {result && (
        <div
          data-reveal
          className="card p-6 flex items-start gap-4"
          style={{ borderColor: "var(--status-pass)" }}
        >
          <div
            className="flex h-10 w-10 items-center justify-center rounded-full"
            style={{ backgroundColor: "rgba(16, 185, 129, 0.1)" }}
          >
            <CheckCircle2 className="h-5 w-5" style={{ color: "var(--status-pass)" }} />
          </div>
          <div className="flex-1">
            <h3
              className="text-base font-semibold mb-2"
              style={{ color: "var(--color-text-primary)" }}
            >
              Override Successfully Recorded
            </h3>
            <div className="flex items-center gap-3 mb-3">
              <Badge
                label={result.original_label}
                tone={LABEL_TONES[result.original_label]}
                size="sm"
              />
              <ArrowRight className="h-4 w-4" style={{ color: "var(--color-text-tertiary)" }} />
              <Badge
                label={result.new_label}
                tone={LABEL_TONES[result.new_label]}
                size="sm"
              />
            </div>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Override ID:{" "}
              <span className="mono-data" style={{ color: "var(--status-pass)" }}>
                {result.id}
              </span>
            </p>
          </div>
          <button
            onClick={() => setResult(null)}
            className="btn btn-ghost"
            style={{ padding: "var(--spacing-2)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Main Content */}
      <div data-reveal className="grid gap-6 lg:grid-cols-[1fr_480px]">
        {/* Left: Form */}
        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <header className="mb-6">
              <h2
                className="font-semibold mb-1"
                style={{
                  fontSize: "var(--font-size-lg)",
                  color: "var(--color-text-primary)",
                }}
              >
                Override Request
              </h2>
            </header>

            {/* Document ID */}
            <div>
              <label
                className="block text-sm font-medium mb-2"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Document ID
              </label>
              <div className="flex gap-2">
                <input
                  id="override-document-id"
                  type="text"
                  value={documentId}
                  onChange={(event) => setDocumentId(event.target.value)}
                  className="input mono-data flex-1"
                  placeholder="Enter document UUID..."
                />
                <button
                  type="button"
                  id="override-load-btn"
                  onClick={() => void loadSnapshot(documentId)}
                  disabled={loadingSnapshot || !documentId.trim()}
                  className="btn btn-secondary"
                >
                  {loadingSnapshot ? "Loading" : "Load"}
                </button>
              </div>
              {loadError && (
                <p
                  className="mt-2 text-sm flex items-center gap-2"
                  style={{ color: "var(--status-fail)" }}
                >
                  <AlertTriangle className="h-4 w-4" />
                  {loadError}
                </p>
              )}
            </div>

            {/* New Label Selector */}
            {snapshotMatchesInput && snapshot && (
              <div className="space-y-6">
                <div>
                  <label
                    className="block text-sm font-medium mb-3"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    Override Classification
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {SENSITIVITY_LABELS.map((label) => {
                      const isSelected = newLabel === label;
                      const isCurrent = label === currentLabel;
                      const color = LABEL_COLORS[label];

                      return (
                        <button
                          key={label}
                          type="button"
                          onClick={() => !isCurrent && setNewLabel(label)}
                          disabled={isCurrent}
                          className="text-left rounded-lg p-3 transition-colors"
                          style={{
                            border: `var(--border-width-hairline) solid ${
                              isSelected ? color : "var(--color-border)"
                            }`,
                            backgroundColor: isSelected
                              ? `rgba(99, 102, 241, 0.05)`
                              : "var(--color-bg-tertiary)",
                            opacity: isCurrent ? 0.5 : 1,
                            cursor: isCurrent ? "not-allowed" : "pointer",
                          }}
                        >
                          <div className="flex items-center justify-between">
                            <span
                              className="text-sm font-medium"
                              style={{
                                color: isSelected
                                  ? color
                                  : "var(--color-text-primary)",
                              }}
                            >
                              {label}
                            </span>
                            {isSelected && !isCurrent && (
                              <CheckCircle2
                                className="h-4 w-4"
                                style={{ color }}
                              />
                            )}
                          </div>
                          {isCurrent && (
                            <span
                              className="text-xs block mt-1"
                              style={{ color: "var(--color-text-tertiary)" }}
                            >
                              (Current)
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Justification */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label
                      className="block text-sm font-medium"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      Justification
                    </label>
                    <span
                      className="text-xs mono-data"
                      style={{ color: charCountColor }}
                    >
                      {justChars}/{MIN_JUSTIFICATION_CHARS} chars
                    </span>
                  </div>
                  <textarea
                    id="override-justification"
                    value={justification}
                    onChange={(event) => setJustification(event.target.value)}
                    rows={4}
                    className="input resize-y"
                    placeholder="Explain why this classification is correct (minimum 20 characters)..."
                  />
                </div>

                {/* Confirmation Warning */}
                <div
                  className="rounded-lg p-4"
                  style={{
                    backgroundColor: "var(--color-bg-tertiary)",
                    border: "var(--border-width-hairline) solid var(--status-override)",
                  }}
                >
                  <div className="flex items-start gap-3 mb-3">
                    <AlertTriangle
                      className="h-5 w-5 flex-shrink-0 mt-0.5"
                      style={{ color: "var(--status-override)" }}
                    />
                    <div className="flex-1">
                      <p
                        className="text-sm font-medium mb-1"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        Permanent Audit Trail
                      </p>
                      <p
                        className="text-xs"
                        style={{
                          color: "var(--color-text-secondary)",
                          lineHeight: "var(--line-height-relaxed)",
                        }}
                      >
                        This override will be permanently logged in the
                        tamper-evident audit chain. The decision, rationale, and
                        your identity will be cryptographically recorded and
                        cannot be deleted or modified.
                      </p>
                    </div>
                  </div>
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      id="override-confirm"
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      className="mt-1 h-4 w-4 rounded cursor-pointer"
                      style={{
                        backgroundColor: "var(--color-bg-primary)",
                        borderColor: "var(--color-border)",
                      }}
                    />
                    <span
                      className="text-sm"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      I understand and confirm this action will be permanently logged
                    </span>
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  id="override-submit-btn"
                  disabled={!canSubmit}
                  className="btn btn-primary w-full py-3"
                  style={{ justifyContent: "center" }}
                >
                  {submitting ? "Submitting Override..." : "Submit Override"}
                </button>

                {submitError && (
                  <div
                    className="p-4 rounded-lg flex items-center gap-3 border-hairline"
                    style={{
                      backgroundColor: "rgba(239, 68, 68, 0.1)",
                      borderColor: "var(--status-fail)",
                    }}
                  >
                    <AlertTriangle
                      className="h-5 w-5 flex-shrink-0"
                      style={{ color: "var(--status-fail)" }}
                    />
                    <p className="text-sm" style={{ color: "var(--status-fail)" }}>
                      {submitError}
                    </p>
                  </div>
                )}
              </div>
            )}
          </form>
        </div>

        {/* Right: Document Details */}
        <div className="space-y-4">
          {snapshotMatchesInput && snapshot ? (
            <div className="card p-6">
              <header className="mb-6">
                <h3
                  className="font-semibold mb-1"
                  style={{
                    fontSize: "var(--font-size-base)",
                    color: "var(--color-text-primary)",
                  }}
                >
                  Current Document State
                </h3>
                <p
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  Effective classification before override
                </p>
              </header>

              <div className="space-y-4">
                {/* Filename */}
                <div
                  className="flex items-center gap-3 p-3 rounded-lg border-hairline"
                  style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                >
                  <FileText
                    className="h-5 w-5"
                    style={{ color: "var(--color-text-secondary)" }}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-xs mb-0.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Filename
                    </p>
                    <p
                      className="text-sm font-medium truncate"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {snapshot.filename}
                    </p>
                  </div>
                </div>

                {/* Current Label */}
                <div>
                  <p
                    className="text-xs mb-2 uppercase tracking-wider"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    Current Classification
                  </p>
                  {snapshot.sensitivity_label ? (
                    <div
                      className="flex items-center justify-between p-4 rounded-lg border-hairline"
                      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                    >
                      <Badge
                        label={snapshot.sensitivity_label}
                        tone={LABEL_TONES[snapshot.sensitivity_label]}
                        size="lg"
                      />
                      {snapshot.label_source && (
                        <span
                          className="text-xs mono-data"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          {snapshot.label_source}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div
                      className="p-4 rounded-lg border-hairline text-center"
                      style={{
                        borderStyle: "dashed",
                        backgroundColor: "var(--color-bg-tertiary)",
                      }}
                    >
                      <p
                        className="text-sm"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        Not classified
                      </p>
                      <p
                        className="text-xs mt-1"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        Cannot override unclassified document
                      </p>
                    </div>
                  )}
                </div>

                {/* Metadata */}
                <div
                  className="pt-4 space-y-2 border-t"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span style={{ color: "var(--color-text-secondary)" }}>
                      Document ID
                    </span>
                    <span
                      className="mono-data text-xs"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {snapshot.id}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span style={{ color: "var(--color-text-secondary)" }}>
                      Status
                    </span>
                    <span
                      className="text-xs uppercase"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {snapshot.current_status}
                    </span>
                  </div>
                  {snapshot.uploaded_at && (
                    <div className="flex items-center justify-between text-sm">
                      <span style={{ color: "var(--color-text-secondary)" }}>
                        Uploaded
                      </span>
                      <span
                        className="text-xs mono-data"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        {new Date(snapshot.uploaded_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>

                {/* View Links */}
                <div className="pt-4 space-y-2">
                  <Link
                    href={`/documents/${snapshot.id}/summary`}
                    className="flex items-center justify-between w-full p-3 rounded-lg border-hairline transition-colors group"
                    style={{
                      backgroundColor: "var(--color-bg-secondary)",
                      color: "var(--color-text-secondary)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "var(--color-bg-hover)";
                      e.currentTarget.style.color = "var(--color-text-primary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                      e.currentTarget.style.color = "var(--color-text-secondary)";
                    }}
                  >
                    <span className="text-sm">View Full Summary</span>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href={`/audit/${snapshot.id}`}
                    className="flex items-center justify-between w-full p-3 rounded-lg border-hairline transition-colors group"
                    style={{
                      backgroundColor: "var(--color-bg-secondary)",
                      color: "var(--color-text-secondary)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "var(--color-bg-hover)";
                      e.currentTarget.style.color = "var(--color-text-primary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                      e.currentTarget.style.color = "var(--color-text-secondary)";
                    }}
                  >
                    <span className="text-sm">View Audit Chain</span>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </div>
          ) : (
            <div
              className="card flex flex-col items-center justify-center py-12"
              style={{ minHeight: "400px" }}
            >
              <FileText
                className="h-12 w-12 mb-4 opacity-40"
                style={{ color: "var(--color-text-tertiary)" }}
              />
              <p
                className="text-base font-medium mb-2"
                style={{ color: "var(--color-text-primary)" }}
              >
                No Document Loaded
              </p>
              <p
                className="text-sm text-center max-w-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Enter a document ID and click Load to view classification details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OverrideFromQuery() {
  const params = useSearchParams();
  const documentId = params.get("document_id") ?? "";
  return <OverrideScreen key={documentId} initialDocumentId={documentId} />;
}

export default function OverridePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Loading override console...
          </p>
        </div>
      }
    >
      <OverrideFromQuery />
    </Suspense>
  );
}
