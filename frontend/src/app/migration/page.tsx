"use client";

import { useState } from "react";
import { ArrowRightLeft, Cpu, Layers } from "lucide-react";

import MetricCard from "@/components/ui/MetricCard";
import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError, rankMigration } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type { MigrationRankResponse } from "@/lib/api/types";

const MIGRATION_ALLOWED = ACCESS.migration;

export default function MigrationPage() {
  const { role } = useRole();
  const permitted = roleAllowed(MIGRATION_ALLOWED, role);
  const [budget, setBudget] = useState("2");
  const [windowDays, setWindowDays] = useState("30");
  const [result, setResult] = useState<MigrationRankResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canRun = permitted && !loading;

  async function handleRank() {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await rankMigration(
          {
            budget: Number(budget),
            window_days: Number(windowDays),
            seed: 42,
          },
          role
        )
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  }

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={MIGRATION_ALLOWED}
          resource="Migration ranking"
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
          Migration Ranking
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          QAOA against greedy and annealing baselines on one identical budget and
          constraint set
        </p>
      </header>

      <div className="card p-5 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span
              className="block text-xs uppercase tracking-wider mb-2"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Budget
            </span>
            <input
              type="number"
              min={0.1}
              step={0.1}
              className="input mono-data w-full"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </label>
          <label className="block">
            <span
              className="block text-xs uppercase tracking-wider mb-2"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Window (days)
            </span>
            <input
              type="number"
              min={1}
              className="input mono-data w-full"
              value={windowDays}
              onChange={(e) => setWindowDays(e.target.value)}
            />
          </label>
        </div>
        <button
          type="button"
          disabled={!canRun}
          onClick={() => void handleRank()}
          className="btn btn-secondary"
        >
          <Cpu className="h-4 w-4" />
          {loading ? "Ranking…" : "Rank with QAOA + baselines"}
        </button>
      </div>

      {error && <ErrorState message={error} onRetry={() => void handleRank()} />}

      {!error && !result && !loading && (
        <EmptyState
          icon={<ArrowRightLeft className="h-8 w-8" />}
          title="No ranking yet"
          message="Set a budget and window, then rank to compare the quantum-optimizer schedule against classical baselines."
        />
      )}

      {result && (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              icon={Cpu}
              value={result.primary.method}
              label="Primary optimizer"
              hint={`${result.schedule.length} document(s) queued`}
              valueColor="var(--crypto-pqc)"
              iconColor="var(--crypto-pqc)"
            />
            <MetricCard
              icon={Layers}
              value={result.primary.total_score}
              label="Total score"
              hint="Higher is better"
            />
            <MetricCard
              icon={Layers}
              value={result.primary.total_cost}
              label="Total cost"
              hint="Under the fixed budget"
            />
          </section>

          <div className="card p-5">
            <h2
              className="font-semibold mb-1"
              style={{
                fontSize: "var(--font-size-lg)",
                color: "var(--color-text-primary)",
              }}
            >
              Baselines
            </h2>
            <p
              className="text-sm mb-4"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Same constraints, same budget — this is the apples-to-apples
              comparison that makes the quantum ranking defensible.
            </p>
            <ul className="space-y-2">
              {result.baselines.map((b) => (
                <li
                  key={b.method}
                  className="flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                >
                  <span
                    className="text-sm font-medium"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {b.method}
                  </span>
                  <span
                    className="mono-data text-sm"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    score {b.total_score} / cost {b.total_cost}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-5">
            <h2
              className="font-semibold mb-4"
              style={{
                fontSize: "var(--font-size-lg)",
                color: "var(--color-text-primary)",
              }}
            >
              Migration schedule
            </h2>
            <ol className="space-y-1.5">
              {result.schedule.map((row) => (
                <li
                  key={row.id}
                  className="flex items-center gap-3 text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  <span
                    className="mono-data inline-flex h-6 w-6 items-center justify-center rounded-full text-xs"
                    style={{
                      backgroundColor: "var(--color-bg-tertiary)",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    {row.priority_rank}
                  </span>
                  <span className="mono-data text-xs">{row.document_id}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}
