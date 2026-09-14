"use client";

import { FormEvent, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, askRag, ingestRagDocument } from "@/lib/api/client";
import type { RagAnswer, UserRole } from "@/lib/api/types";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "security_analyst", label: "Security Analyst" },
  { value: "security_admin", label: "Security Admin" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
];

export default function AskPage() {
  const [role, setRole] = useState<UserRole>("security_analyst");
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

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Ask</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              FR-11 · grounded Q&A (Planner → Retriever → Reasoner → Verifier)
            </p>
          </div>
          <SiteNav active="/ask" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-6">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Answers are refused unless the Verifier can ground them in ingested
          inventory/audit records. Embeddings use the labelled stub{" "}
          <code>stub-hash-v1</code>.
        </p>

        <div>
          <label htmlFor="ask-role" className="block text-xs mb-1.5">
            Caller Role
          </label>
          <select
            id="ask-role"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="ask-doc" className="block text-xs mb-1.5">
            Document id
          </label>
          <input
            id="ask-doc"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="w-full max-w-xl rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
            placeholder="uuid"
          />
        </div>

        <form onSubmit={handleIngest}>
          <button
            type="submit"
            disabled={busy || !documentId.trim()}
            className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm disabled:opacity-50"
          >
            Ingest document records
          </button>
        </form>
        {ingestNote && <p className="text-sm text-emerald-400">{ingestNote}</p>}

        <form onSubmit={handleAsk} className="space-y-3">
          <label htmlFor="ask-q" className="block text-xs mb-1.5">
            Question
          </label>
          <textarea
            id="ask-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            className="w-full max-w-2xl rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 3}
            className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Ask (verified)
          </button>
        </form>

        {error && <p className="text-sm text-red-400">{error}</p>}
        {answer && (
          <section className="space-y-2 rounded-xl border border-[var(--color-border)] p-4">
            <p className="text-xs text-[var(--color-text-muted)]">
              Plan: {answer.plan}
            </p>
            {answer.verified ? (
              <p className="text-sm whitespace-pre-wrap">{answer.answer}</p>
            ) : (
              <p className="text-sm text-amber-400">
                Refused: {answer.refusal_reason}
              </p>
            )}
            {answer.citations.length > 0 && (
              <ul className="text-xs space-y-1 text-[var(--color-text-secondary)]">
                {answer.citations.map((c) => (
                  <li key={c.chunk_id}>
                    [{c.source_type}] score={c.score.toFixed(3)} —{" "}
                    {c.content.slice(0, 160)}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
