"use client";

import { useState } from "react";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, rankMigration } from "@/lib/api/client";
import type { MigrationRankResponse, UserRole } from "@/lib/api/types";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "security_admin", label: "Security Admin" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "data_owner", label: "Data Owner" },
];

export default function MigrationPage() {
  const [role, setRole] = useState<UserRole>("security_admin");
  const [budget, setBudget] = useState("2");
  const [windowDays, setWindowDays] = useState("30");
  const [result, setResult] = useState<MigrationRankResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canRun = role === "security_admin" && !loading;

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

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold"
            >
              Q
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Migration ranking
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                FR-9 QAOA + classical baselines under one budget
              </p>
            </div>
          </div>
          <SiteNav active="/migration" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-8 space-y-6">
        <label className="block text-sm">
          <span className="text-[var(--color-text-secondary)]">Caller role</span>
          <select
            className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
          >
            {ROLES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm">
            <span className="text-[var(--color-text-secondary)]">Budget</span>
            <input
              type="number"
              min={0.1}
              step={0.1}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--color-text-secondary)]">
              Window (days)
            </span>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2"
              value={windowDays}
              onChange={(e) => setWindowDays(e.target.value)}
            />
          </label>
        </div>

        <button
          type="button"
          disabled={!canRun}
          onClick={() => void handleRank()}
          className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {loading ? "Ranking…" : "Rank with QAOA + baselines"}
        </button>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {result && (
          <div className="space-y-4 text-sm">
            <div>
              <h2 className="font-semibold">Primary ({result.primary.method})</h2>
              <p className="text-[var(--color-text-secondary)]">
                score {result.primary.total_score} / cost{" "}
                {result.primary.total_cost} — {result.schedule.length} queued
              </p>
            </div>
            <div>
              <h2 className="font-semibold">Baselines (same constraints)</h2>
              <ul className="mt-1 space-y-1 text-[var(--color-text-secondary)]">
                {result.baselines.map((b) => (
                  <li key={b.method}>
                    {b.method}: score {b.total_score} / cost {b.total_cost}
                  </li>
                ))}
              </ul>
            </div>
            <ol className="list-decimal pl-5 space-y-1 font-mono text-xs">
              {result.schedule.map((row) => (
                <li key={row.id}>
                  rank {row.priority_rank}: {row.document_id}
                </li>
              ))}
            </ol>
          </div>
        )}
      </main>
    </div>
  );
}
