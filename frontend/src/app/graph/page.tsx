"use client";

import { FormEvent, useEffect, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import {
  ApiError,
  getDocumentAttackPaths,
  getGraphStatus,
  seedGraph,
} from "@/lib/api/client";
import type { AttackPathResponse, GraphSeedResponse, UserRole } from "@/lib/api/types";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "security_admin", label: "Security Admin" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

export default function GraphPage() {
  const [role, setRole] = useState<UserRole>("security_admin");
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [seedResult, setSeedResult] = useState<GraphSeedResponse | null>(null);
  const [paths, setPaths] = useState<AttackPathResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void getGraphStatus()
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(false));
  }, []);

  async function handleSeed(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await seedGraph(
        { document_id: documentId.trim() || null },
        role
      );
      setSeedResult(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  async function handlePaths(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await getDocumentAttackPaths(documentId.trim(), role);
      setPaths(result);
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
            <h1 className="text-lg font-semibold tracking-tight">
              Knowledge Graph
            </h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              FR-10 · multi-hop attack paths (Neo4j)
            </p>
          </div>
          <SiteNav active="/graph" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-6">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Neo4j configured:{" "}
          {configured === null ? "…" : configured ? "yes" : "no — set QAEGIS_NEO4J_*"}
        </p>

        <div>
          <label htmlFor="graph-role" className="block text-xs mb-1.5">
            Caller Role
          </label>
          <select
            id="graph-role"
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

        <form onSubmit={handleSeed} className="space-y-3">
          <label htmlFor="graph-doc" className="block text-xs mb-1.5">
            Document id (optional for seed; required for paths)
          </label>
          <input
            id="graph-doc"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="w-full max-w-xl rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
            placeholder="uuid"
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Seed demo graph
            </button>
            <button
              type="button"
              disabled={busy || !documentId.trim()}
              onClick={(e) => void handlePaths(e as unknown as FormEvent)}
              className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm disabled:opacity-50"
            >
              Load attack paths
            </button>
          </div>
        </form>

        {error && <p className="text-sm text-red-400">{error}</p>}
        {seedResult && (
          <p className="text-sm">
            Seeded {seedResult.nodes_upserted} nodes,{" "}
            {seedResult.relationships_upserted} relationships
            {seedResult.demo ? " (demo)" : ""}.
          </p>
        )}
        {paths && (
          <section className="space-y-3">
            <h2 className="text-base font-semibold">Paths</h2>
            {paths.note && (
              <p className="text-sm text-[var(--color-text-muted)]">{paths.note}</p>
            )}
            {paths.paths.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">No paths.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {paths.paths.map((p) => (
                  <li
                    key={p.summary}
                    className="rounded-lg border border-[var(--color-border)] p-3"
                  >
                    <div className="font-medium">{p.summary}</div>
                    <div className="text-[var(--color-text-muted)] text-xs mt-1">
                      {p.hops} hop(s) · {p.relationships.join(", ")}
                    </div>
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
