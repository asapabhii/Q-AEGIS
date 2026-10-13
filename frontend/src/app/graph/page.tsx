"use client";

import { FormEvent, useEffect, useState } from "react";
import { Network, Route, Sprout } from "lucide-react";

import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState } from "@/components/ui/states";
import StatusDot from "@/components/ui/StatusDot";
import {
  ApiError,
  getDocumentAttackPaths,
  getGraphStatus,
  seedGraph,
} from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type { AttackPathResponse, GraphSeedResponse } from "@/lib/api/types";

const GRAPH_ALLOWED = ACCESS.graph;

export default function GraphPage() {
  const { role } = useRole();
  const permitted = roleAllowed(GRAPH_ALLOWED, role);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [seedResult, setSeedResult] = useState<GraphSeedResponse | null>(null);
  const [paths, setPaths] = useState<AttackPathResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!permitted) return;
    void getGraphStatus()
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(false));
  }, [permitted]);

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

  async function handlePaths() {
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

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={GRAPH_ALLOWED}
          resource="The attack graph"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-screen-xl px-6 py-8 space-y-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1
            className="font-semibold mb-1"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            Attack Graph
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            Multi-hop attack paths across documents, actors, and devices (Neo4j)
          </p>
        </div>
        <StatusDot
          variant={configured ? "online" : "offline"}
          label={
            configured === null
              ? "Checking Neo4j…"
              : configured
                ? "Neo4j connected"
                : "Neo4j not configured"
          }
        />
      </header>

      <div className="card p-5 space-y-4">
        <label className="block">
          <span
            className="block text-xs uppercase tracking-wider mb-2"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Document ID (optional to seed, required for paths)
          </span>
          <input
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="input mono-data w-full"
            placeholder="Enter document UUID..."
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={(e) => void handleSeed(e as unknown as FormEvent)}
            className="btn btn-secondary"
          >
            <Sprout className="h-4 w-4" />
            Seed demo graph
          </button>
          <button
            type="button"
            disabled={busy || !documentId.trim()}
            onClick={() => void handlePaths()}
            className="btn btn-secondary"
          >
            <Route className="h-4 w-4" />
            Load attack paths
          </button>
        </div>
        {seedResult && (
          <p className="text-sm" style={{ color: "var(--status-pass)" }}>
            Seeded {seedResult.nodes_upserted} nodes,{" "}
            {seedResult.relationships_upserted} relationships
            {seedResult.demo ? " (demo)" : ""}.
          </p>
        )}
      </div>

      {error && <ErrorState message={error} onRetry={() => void handlePaths()} />}

      {paths && (
        <section className="space-y-3">
          {paths.note && (
            <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
              {paths.note}
            </p>
          )}
          {paths.paths.length === 0 ? (
            <EmptyState
              icon={<Network className="h-8 w-8" />}
              title="No attack paths found"
              message="No multi-hop route reaches this document in the current graph. Seed the demo graph or ingest more relationships."
            />
          ) : (
            <ul className="space-y-2">
              {paths.paths.map((p) => (
                <li key={p.summary} className="card p-4">
                  <div
                    className="text-sm font-medium"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {p.summary}
                  </div>
                  <div
                    className="text-xs mt-1"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    {p.hops} hop(s) · {p.relationships.join(", ")}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
