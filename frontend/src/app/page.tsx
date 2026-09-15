"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Upload,
  FileText,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  X,
} from "lucide-react";
import Badge from "@/components/ui/Badge";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import {
  checkHealth,
  registerAndClassify,
  ApiError,
} from "@/lib/api/client";
import type {
  HealthResponse,
  ClassificationResponse,
  DocumentResponse,
} from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Role descriptions — authorization plumbing, NOT authentication
// ---------------------------------------------------------------------------

const LABEL_TONES: Record<
  string,
  "public" | "internal" | "confidential" | "restricted"
> = {
  PUBLIC: "public",
  INTERNAL: "internal",
  CONFIDENTIAL: "confidential",
  RESTRICTED: "restricted",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ClassifyPage() {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Health
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Classify flow
  const { role } = useRole();
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [registeredDocument, setRegisteredDocument] =
    useState<DocumentResponse | null>(null);
  const [classification, setClassification] =
    useState<ClassificationResponse | null>(null);
  const [classifyError, setClassifyError] = useState<string | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  // ------ Health check ------
  const handleHealthCheck = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const res = await checkHealth();
      setHealth(res);
    } catch (err) {
      setHealthError(err instanceof ApiError ? err.message : "Network error");
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
      setClassifyError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setClassifyLoading(false);
    }
  }, [filename, content, role]);

  // ------ Drag & Drop handlers ------
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const file = files[0];
      setFilename(file.name);
      
      // Read file content (for demo, just use placeholder)
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setContent(text.slice(0, 500)); // First 500 chars
      };
      reader.readAsText(file);
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      setFilename(file.name);
      
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setContent(text.slice(0, 500));
      };
      reader.readAsText(file);
    }
  }, []);

  const handleReset = useCallback(() => {
    setRegisteredDocument(null);
    setClassification(null);
    setClassifyError(null);
    setContent("");
    setFilename("");
  }, []);

  return (
    <div
      ref={containerRef}
      className="mx-auto w-full max-w-[1600px] space-y-8 px-6 py-8"
    >
      {/* Hero Header */}
      <header data-reveal>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1
              className="font-semibold mb-1"
              style={{
                fontSize: "var(--font-size-2xl)",
                color: "var(--color-text-primary)",
              }}
            >
              Upload Document
            </h1>
            <p
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-secondary)",
              }}
            >
              Register documents and classify their sensitivity in real-time
            </p>
          </div>

          {/* System Status */}
          <div className="flex items-center gap-3">
            <div
              className={`status-dot ${
                health ? "status-dot-pass" : "status-dot-pending"
              }`}
            />
            <div className="text-sm">
              <p style={{ color: "var(--color-text-primary)", fontWeight: 500 }}>
                {health ? "System Online" : "Status Unknown"}
              </p>
              {health && (
                <p className="mono-data" style={{ color: "var(--color-text-tertiary)" }}>
                  v{health.version}
                </p>
              )}
            </div>
            <button
              onClick={handleHealthCheck}
              disabled={healthLoading}
              className="btn btn-secondary ml-2"
            >
              {healthLoading ? "..." : "Check"}
            </button>
          </div>
        </div>
        {healthError && (
          <div
            className="p-3 rounded-md text-sm border-hairline"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              borderColor: "var(--status-fail)",
              color: "var(--status-fail)",
            }}
          >
            {healthError}
          </div>
        )}
      </header>

      {/* Main Upload Zone or Results */}
      {!registeredDocument && !classification ? (
        <>
          {/* Upload Zone */}
          <div data-reveal className="card p-6">
            <div className="space-y-6">
              {/* Drag & Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className="rounded-lg p-12 text-center cursor-pointer transition-colors"
                style={{
                  minHeight: "280px",
                  border: "var(--border-width-default) dashed var(--color-border)",
                  backgroundColor: isDragOver
                    ? "var(--color-bg-hover)"
                    : "var(--color-bg-secondary)",
                }}
              >
                <div className="flex flex-col items-center justify-center h-full">
                  <Upload
                    className="h-12 w-12 mx-auto mb-4"
                    style={{ color: "var(--color-text-tertiary)" }}
                  />

                  {isDragOver ? (
                    <div>
                      <p
                        className="text-base font-medium mb-1"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        Release to Upload
                      </p>
                      <p
                        className="text-sm"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        Drop your document here
                      </p>
                    </div>
                  ) : (
                    <>
                      <p
                        className="text-base font-medium mb-1"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        Drag & Drop Document
                      </p>
                      <p
                        className="text-sm mb-4"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        or click to browse files
                      </p>
                      <div
                        className="flex items-center gap-2 text-xs"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        <FileText className="h-4 w-4" />
                        <span>Supported: PDF, DOCX, TXT, CSV</span>
                      </div>
                    </>
                  )}
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.txt,.csv"
                  onChange={handleFileSelect}
                />
              </div>

              {/* Manual Input Toggle */}
              {filename && (
                <div className="space-y-4">
                  <div
                    className="flex items-center justify-between p-4 rounded-lg border-hairline"
                    style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                  >
                    <div className="flex items-center gap-3">
                      <FileText
                        className="h-5 w-5"
                        style={{ color: "var(--color-text-secondary)" }}
                      />
                      <div>
                        <p
                          className="text-sm font-medium"
                          style={{ color: "var(--color-text-primary)" }}
                        >
                          {filename}
                        </p>
                        <p
                          className="text-xs"
                          style={{ color: "var(--color-text-tertiary)" }}
                        >
                          {content.length} characters loaded
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={handleReset}
                      className="btn btn-ghost"
                      style={{ padding: "var(--spacing-2)" }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Content Preview */}
                  <div>
                    <label
                      className="block text-sm font-medium mb-2"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      Content Preview
                    </label>
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      rows={6}
                      className="input mono-data resize-y"
                      placeholder="Document content will appear here..."
                    />
                  </div>

                  {/* Classify Button */}
                  <button
                    onClick={handleClassify}
                    disabled={classifyLoading || !content.trim()}
                    className="btn btn-primary w-full py-3"
                    style={{ justifyContent: "center" }}
                  >
                    {classifyLoading ? (
                      "Analyzing Document..."
                    ) : (
                      "Register & Classify Document"
                    )}
                  </button>

                  {classifyError && (
                    <div
                      className="p-4 rounded-lg border-hairline flex items-center gap-3"
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
                        {classifyError}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div data-reveal className="space-y-6">
          {/* Success Banner */}
          <div
            className="card p-6 flex items-center justify-between"
            style={{ borderColor: "var(--status-pass)" }}
          >
            <div className="flex items-center gap-4">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ backgroundColor: "rgba(16, 185, 129, 0.1)" }}
              >
                <CheckCircle
                  className="h-5 w-5"
                  style={{ color: "var(--status-pass)" }}
                />
              </div>
              <div>
                <h3
                  className="text-base font-semibold mb-1"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  Classification Complete
                </h3>
                <p
                  className="text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Document successfully registered and analyzed
                </p>
              </div>
            </div>
            <button onClick={handleReset} className="btn btn-secondary">
              Upload Another
            </button>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Document Info */}
            {registeredDocument && (
              <div className="card p-6">
                <header className="mb-6">
                  <h3
                    className="font-semibold mb-1"
                    style={{
                      fontSize: "var(--font-size-base)",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    Document Registered
                  </h3>
                  <p
                    style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    System-assigned identifier and metadata
                  </p>
                </header>
                <dl className="space-y-4">
                  <div>
                    <dt
                      className="text-xs mb-1.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Document ID
                    </dt>
                    <dd
                      className="mono-data text-sm"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {registeredDocument.id}
                    </dd>
                  </div>
                  <div>
                    <dt
                      className="text-xs mb-1.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Filename
                    </dt>
                    <dd
                      className="text-sm"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {registeredDocument.filename}
                    </dd>
                  </div>
                  <div>
                    <dt
                      className="text-xs mb-1.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Status
                    </dt>
                    <dd>
                      <Badge
                        label={registeredDocument.current_status}
                        tone="info"
                        size="sm"
                      />
                    </dd>
                  </div>
                  <div>
                    <dt
                      className="text-xs mb-1.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Uploaded At
                    </dt>
                    <dd
                      className="text-sm mono-data"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {new Date(registeredDocument.uploaded_at).toLocaleString()}
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            {/* Classification Result */}
            {classification && (
              <div className="card p-6">
                <header className="mb-6">
                  <h3
                    className="font-semibold mb-1"
                    style={{
                      fontSize: "var(--font-size-base)",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    Classification Analysis
                  </h3>
                  <p
                    style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    AI-powered sensitivity assessment
                  </p>
                </header>

                {/* Hero Badge */}
                <div className="mb-6 flex items-center gap-3">
                  <Badge
                    label={classification.sensitivity_label}
                    tone={LABEL_TONES[classification.sensitivity_label]}
                    size="lg"
                  />
                  {classification.is_defaulted && (
                    <div
                      className="flex items-center gap-1.5 px-3 py-1 rounded-full border-hairline"
                      style={{
                        backgroundColor: "rgba(249, 115, 22, 0.1)",
                        borderColor: "var(--status-override)",
                      }}
                    >
                      <AlertTriangle
                        className="h-3.5 w-3.5"
                        style={{ color: "var(--status-override)" }}
                      />
                      <span
                        className="text-xs font-medium"
                        style={{ color: "var(--status-override)" }}
                      >
                        Fail-Safe Escalated
                      </span>
                    </div>
                  )}
                </div>

                <dl className="space-y-4">
                  {/* Confidence */}
                  <div>
                    <dt
                      className="text-xs mb-2 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Confidence Level
                    </dt>
                    <dd>
                      <div className="flex items-center gap-3 mb-1">
                        <div
                          className="flex-1 h-2 rounded-full overflow-hidden"
                          style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                        >
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${classification.confidence * 100}%`,
                              backgroundColor: "var(--status-info)",
                            }}
                          />
                        </div>
                        <span
                          className="mono-data text-lg font-semibold"
                          style={{ color: "var(--color-text-primary)" }}
                        >
                          {(classification.confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p
                        className="text-xs"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        Threshold: {(classification.confidence_threshold * 100).toFixed(0)}%
                      </p>
                    </dd>
                  </div>

                  {/* Model */}
                  <div>
                    <dt
                      className="text-xs mb-1.5 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Model Version
                    </dt>
                    <dd
                      className="mono-data text-xs"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {classification.model_version}
                    </dd>
                  </div>

                  {/* Keywords */}
                  {classification.matched_keywords.length > 0 && (
                    <div>
                      <dt
                        className="text-xs mb-2 uppercase tracking-wider"
                        style={{ color: "var(--color-text-tertiary)" }}
                      >
                        Matched Keywords
                      </dt>
                      <dd className="flex flex-wrap gap-2">
                        {classification.matched_keywords.map((kw) => (
                          <span
                            key={kw}
                            className="px-2.5 py-1 rounded-md border-hairline text-xs mono-data"
                            style={{
                              backgroundColor: "var(--color-bg-tertiary)",
                              color: "var(--color-text-secondary)",
                            }}
                          >
                            {kw}
                          </span>
                        ))}
                      </dd>
                    </div>
                  )}

                  {/* Rationale */}
                  <div>
                    <dt
                      className="text-xs mb-2 uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      AI Rationale
                    </dt>
                    <dd
                      className="text-sm rounded-lg p-4 border-hairline"
                      style={{
                        backgroundColor: "var(--color-bg-tertiary)",
                        color: "var(--color-text-secondary)",
                        lineHeight: "var(--line-height-relaxed)",
                      }}
                    >
                      {classification.rationale}
                    </dd>
                  </div>
                </dl>

                {/* Action Buttons */}
                {registeredDocument && (
                  <div
                    className="mt-6 pt-6 space-y-3"
                    style={{ borderTop: "var(--border-width-hairline) solid var(--color-border)" }}
                  >
                    <Link
                      href={`/override?document_id=${registeredDocument.id}`}
                      className="btn btn-secondary w-full py-2"
                      style={{ justifyContent: "center" }}
                    >
                      Override Classification
                      <ArrowRight className="h-4 w-4 ml-1" />
                    </Link>
                    <Link
                      href={`/dashboard`}
                      className="btn btn-ghost w-full py-2"
                      style={{ justifyContent: "center" }}
                    >
                      View Dashboard
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

