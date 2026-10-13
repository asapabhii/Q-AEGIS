"use client";

import { FormEvent, useState } from "react";
import { MessageSquare, ShieldCheck, ShieldAlert } from "lucide-react";

import NotPermitted from "@/components/ui/NotPermitted";
import { ErrorState } from "@/components/ui/states";
import { ApiError, askRag, ingestRagDocument } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type { RagAnswer } from "@/lib/api/types";

const ASK_ALLOWED = ACCESS.ask;

export default function AskPage() {
  const { role } = useRole();
  const permitted = roleAllowed(ASK_ALLOWED, role);
  const [documentId, setDocumentId] = useState("");
  const [question, setQuestion] = useState(
    "What is the current sensitivity and protection for this document?"
  );
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ingestNote, setIngestNote] = useState<string | null>(null);

  async function handleIngest(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setIngestNote(null);
    try {
      const result = await ingestRagDocument(documentId.trim(), role);
      setIngestNote(
        `Indexed ${result.chunks_written} chunk(s) with ${result.embedding_model}.`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await askRag(
        {
          question: question.trim(),
          document_id: documentId.trim() || null,
        },
        role
      );
      setAnswer(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={ASK_ALLOWED}
          resource="The grounded assistant"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-screen-xl px-6 py-8 space-y-8">
      <header>
        <h1
          className="font-semibold mb-1"
          style={{
            fontSize: "var(--font-size-2xl)",
            color: "var(--color-text-primary)",
          }}
        >
          Assistant
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Grounded Q&amp;A over inventory and audit records — Planner → Retriever →
          Reasoner → Verifier. Answers are refused unless the Verifier can ground
          them.
        </p>
      </header>

      <div className="card p-5 space-y-4">
        <label className="block">
          <span
            className="block text-xs uppercase tracking-wider mb-2"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Document ID
          </span>
          <input
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="input mono-data w-full"
            placeholder="Enter document UUID..."
          />
        </label>
        <form onSubmit={handleIngest}>
          <button
            type="submit"
            disabled={busy || !documentId.trim()}
            className="btn btn-secondary"
          >
            Ingest document records
          </button>
        </form>
        {ingestNote && (
          <p className="text-sm" style={{ color: "var(--status-pass)" }}>
            {ingestNote}
          </p>
        )}
      </div>

      <form onSubmit={handleAsk} className="card p-5 space-y-4">
        <label className="block">
          <span
            className="block text-xs uppercase tracking-wider mb-2"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Question
          </span>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            className="input w-full"
          />
        </label>
        <button
          type="submit"
          disabled={busy || question.trim().length < 3}
          className="btn btn-primary"
        >
          <MessageSquare className="h-4 w-4" />
          {busy ? "Asking…" : "Ask (verified)"}
        </button>
      </form>

      {error && <ErrorState message={error} />}

      {answer && (
        <section className="card p-5 space-y-4">
          <div className="flex items-center gap-2">
            {answer.verified ? (
              <>
                <ShieldCheck
                  className="h-5 w-5"
                  style={{ color: "var(--status-pass)" }}
                />
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--status-pass)" }}
                >
                  Verified answer
                </span>
              </>
            ) : (
              <>
                <ShieldAlert
                  className="h-5 w-5"
                  style={{ color: "var(--status-override)" }}
                />
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--status-override)" }}
                >
                  Refused — not grounded
                </span>
              </>
            )}
          </div>

          {answer.verified ? (
            <p
              className="text-sm whitespace-pre-wrap"
              style={{
                color: "var(--color-text-primary)",
                lineHeight: "var(--line-height-relaxed)",
              }}
            >
              {answer.answer}
            </p>
          ) : (
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {answer.refusal_reason}
            </p>
          )}

          <div
            className="flex flex-wrap gap-x-4 gap-y-1 text-xs pt-2"
            style={{
              color: "var(--color-text-tertiary)",
              borderTop: "1px solid var(--color-border)",
            }}
          >
            <span>Plan: {answer.plan}</span>
            <span className="mono-data">
              Embedding: {answer.embedding_model}
            </span>
          </div>

          {answer.citations.length > 0 && (
            <ul className="space-y-2">
              {answer.citations.map((c) => (
                <li
                  key={c.chunk_id}
                  className="rounded-lg px-3 py-2 text-xs"
                  style={{
                    backgroundColor: "var(--color-bg-tertiary)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  <span
                    className="mono-data"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    [{c.source_type}] score={c.score.toFixed(3)}
                  </span>{" "}
                  — {c.content.slice(0, 200)}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
