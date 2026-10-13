"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Shield,
  Scale,
  Radar,
  Atom,
  Leaf,
  Cpu,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";

import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { ApiError, getDocumentAgents } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type { AgentDeepDiveResponse, AgentType } from "@/lib/api/types";

const AGENT_META: Record<
  AgentType,
  { label: string; icon: typeof Shield; blurb: string }
> = {
  security: {
    label: "Security",
    icon: Shield,
    blurb: "Threat exposure and access sensitivity",
  },
  compliance: {
    label: "Compliance",
    icon: Scale,
    blurb: "Regulatory and retention obligations",
  },
  contextual: {
    label: "Contextual",
    icon: Radar,
    blurb: "Actor, device, and time-of-access risk",
  },
  quantum: {
    label: "Quantum Readiness",
    icon: Atom,
    blurb: "Harvest-now-decrypt-later exposure",
  },
  sustainability: {
    label: "Sustainability",
    icon: Leaf,
    blurb: "Compute and energy cost of protection",
  },
};

function scoreColor(score: number): string {
  if (score >= 0.7) return "var(--status-fail)";
  if (score >= 0.5) return "var(--status-override)";
  return "var(--status-pass)";
}

const AGENTS_ALLOWED = ACCESS.inventory;

function AgentsInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { role } = useRole();
  const permitted = roleAllowed(AGENTS_ALLOWED, role);
  const queryId = params.get("document_id") ?? "";
  const [documentId, setDocumentId] = useState(queryId);
  const [data, setData] = useState<AgentDeepDiveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDocumentId(queryId);
  }, [queryId]);

  const load = useCallback(
    (id: string) => {
      const trimmed = id.trim();
      if (!permitted || !trimmed) return () => {};
      let cancelled = false;
      setLoading(true);
      setError(null);
      setData(null);
      getDocumentAgents(trimmed, role)
        .then((res) => {
          if (!cancelled) setData(res);
        })
        .catch((err: unknown) => {
          if (!cancelled)
            setError(err instanceof ApiError ? err.message : "Network error");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    },
    [permitted, role]
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    return load(queryId);
  }, [load, queryId]);

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={AGENTS_ALLOWED}
          resource="Agent analysis"
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
          Agent Analysis
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Per-agent scores and rationales behind the consensus Trust Score
        </p>
      </header>

      {/* Document selector */}
      <div className="card p-4">
        <label
          htmlFor="agents-document-id"
          className="block text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          Document ID
        </label>
        <div className="flex gap-2">
          <input
            id="agents-document-id"
            type="text"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter")
                router.push(
                  `/agents?document_id=${encodeURIComponent(documentId.trim())}`
                );
            }}
            className="input mono-data flex-1"
            placeholder="Enter document UUID..."
          />
          <button
            type="button"
            onClick={() =>
              router.push(
                `/agents?document_id=${encodeURIComponent(documentId.trim())}`
              )
            }
            disabled={!documentId.trim() || loading}
            className="btn btn-secondary"
          >
            {loading ? "Loading" : "Analyze"}
          </button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => load(documentId)} />}

      {!error && !queryId && !loading && (
        <EmptyState
          icon={<Cpu className="h-8 w-8" />}
          title="No document selected"
          message="Enter a document ID above, or open Agent Analysis from a document's fleet or dashboard row."
        />
      )}

      {loading && (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      )}

      {!loading && data && (
        <>
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
            style={{ color: "var(--color-text-secondary)" }}
          >
            <span className="mono-data text-xs">{data.document_id}</span>
            {data.assessed_at && (
              <span style={{ color: "var(--color-text-tertiary)" }}>
                Assessed {new Date(data.assessed_at).toLocaleString()}
              </span>
            )}
          </div>

          {data.note && (
            <div
              className="card p-4 flex items-start gap-3"
              style={{ borderColor: "var(--status-override)" }}
            >
              <AlertTriangle
                className="h-5 w-5 flex-shrink-0"
                style={{ color: "var(--status-override)" }}
              />
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {data.note}
              </p>
            </div>
          )}

          {data.agents.length === 0 ? (
            <EmptyState
              icon={<Cpu className="h-8 w-8" />}
              title="No agent scores yet"
              message="This document has not been through the scoring pipeline, or the risk assessment is still pending."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {data.agents.map((agent) => {
                const meta = AGENT_META[agent.agent_type];
                const Icon = meta?.icon ?? Cpu;
                const numeric = Number(agent.score);
                const pct = Number.isFinite(numeric)
                  ? Math.max(0, Math.min(1, numeric)) * 100
                  : 0;
                const color = Number.isFinite(numeric)
                  ? scoreColor(numeric)
                  : "var(--color-text-tertiary)";
                return (
                  <div key={agent.id} className="card p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <Icon
                          className="h-4 w-4"
                          style={{ color: "var(--color-text-secondary)" }}
                        />
                        <div>
                          <p
                            className="text-sm font-semibold"
                            style={{ color: "var(--color-text-primary)" }}
                          >
                            {meta?.label ?? agent.agent_type}
                          </p>
                          <p
                            className="text-xs"
                            style={{ color: "var(--color-text-tertiary)" }}
                          >
                            {meta?.blurb ?? "Scoring agent"}
                          </p>
                        </div>
                      </div>
                      <span
                        className="mono-data text-lg font-semibold"
                        style={{ color }}
                      >
                        {Number.isFinite(numeric) ? numeric.toFixed(2) : agent.score}
                      </span>
                    </div>
                    <div
                      className="h-1.5 rounded-full overflow-hidden mb-3"
                      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                    >
                      <div
                        className="h-full transition-all duration-500"
                        style={{ width: `${pct}%`, backgroundColor: color }}
                      />
                    </div>
                    <p
                      className="text-sm"
                      style={{
                        color: "var(--color-text-secondary)",
                        lineHeight: "var(--line-height-relaxed)",
                      }}
                    >
                      {agent.rationale}
                    </p>
                  </div>
                );
              })}
            </div>
          )}

          {data.missing_agents.length > 0 && (
            <div
              className="card p-4 flex items-start gap-3"
              style={{ borderColor: "var(--status-override)" }}
            >
              <AlertTriangle
                className="h-5 w-5 flex-shrink-0"
                style={{ color: "var(--status-override)" }}
              />
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                Fail-safe: {data.missing_agents.length} agent
                {data.missing_agents.length === 1 ? "" : "s"} did not report
                within timeout —{" "}
                <span style={{ color: "var(--color-text-primary)" }}>
                  {data.missing_agents
                    .map((a) => AGENT_META[a]?.label ?? a)
                    .join(", ")}
                </span>
                . Consensus proceeded on the agents that responded.
              </p>
            </div>
          )}

          <Link
            href={`/audit/${data.document_id}`}
            className="btn btn-secondary"
          >
            Open Audit Chain
            <ArrowRight className="h-4 w-4" />
          </Link>
        </>
      )}
    </div>
  );
}

export default function AgentsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Loading agent analysis...
          </p>
        </div>
      }
    >
      <AgentsInner />
    </Suspense>
  );
}
