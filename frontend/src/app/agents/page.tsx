"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, getDocumentAgents } from "@/lib/api/client";
import type { AgentDeepDiveResponse } from "@/lib/api/types";
import { getSessionUser } from "@/lib/auth/session";

function AgentsInner() {
  const params = useSearchParams();
  const documentId = params.get("document_id") ?? "";
  const session = typeof window !== "undefined" ? getSessionUser() : null;
  const role = session?.role ?? "security_admin";
  const [data, setData] = useState<AgentDeepDiveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) return;
    getDocumentAgents(documentId, role)
      .then(setData)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Network error")
      );
  }, [documentId, role]);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">Agent deep-dive</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              Scores, rationales, and missing agents
            </p>
          </div>
          <SiteNav active="/dashboard" />
        </div>
      </header>
      <main className="flex-1 mx-auto w-full max-w-3xl px-6 py-8 space-y-4">
        {!documentId && (
          <p className="text-sm text-[var(--color-text-muted)]">
            Pass <code>document_id</code> in the query string.
          </p>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}
        {data && (
          <>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Document {data.document_id}
              {data.assessed_at ? ` · assessed ${data.assessed_at}` : ""}
            </p>
            {data.note && (
              <p className="text-sm text-amber-400">{data.note}</p>
            )}
            <ul className="space-y-3">
              {data.agents.map((agent) => (
                <li
                  key={agent.id}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4"
                >
                  <div className="flex justify-between text-sm font-semibold mb-2">
                    <span>{agent.agent_type}</span>
                    <span className="font-mono">{agent.score}</span>
                  </div>
                  <p className="text-sm text-[var(--color-text-secondary)]">
                    {agent.rationale}
                  </p>
                </li>
              ))}
            </ul>
            {data.missing_agents.length > 0 && (
              <p className="text-sm text-[var(--color-text-muted)]">
                Missing: {data.missing_agents.join(", ")}
              </p>
            )}
            <Link
              href={`/audit?document_id=${data.document_id}`}
              className="text-cyan-400 text-sm hover:underline"
            >
              Open audit chain →
            </Link>
          </>
        )}
      </main>
    </div>
  );
}

export default function AgentsPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <AgentsInner />
    </Suspense>
  );
}
