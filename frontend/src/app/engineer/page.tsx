"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Server,
  Database,
  RefreshCw,
  ArrowUpRight,
} from "lucide-react";

import DataTable from "@/components/ui/DataTable";
import MetricCard from "@/components/ui/MetricCard";
import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { ApiError, checkHealth, listDocuments } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type {
  DocumentInventoryResponse,
  HealthResponse,
} from "@/lib/api/types";

const HEALTH_ALLOWED = ACCESS.engineer;

export default function EngineerPage() {
  const { role } = useRole();
  // The inventory read is gated server-side; send the caller's real role and
  // render an honest 403 rather than defaulting anyone to "engineer".
  const permitted = roleAllowed(HEALTH_ALLOWED, role);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [inventory, setInventory] = useState<DocumentInventoryResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!permitted) {
      setLoading(false);
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([checkHealth(), listDocuments(role)])
      .then(([h, inv]) => {
        if (cancelled) return;
        setHealth(h);
        setInventory(inv);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role, permitted]);

  useEffect(() => load(), [load]);

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={HEALTH_ALLOWED}
          resource="The system health view"
        />
      </div>
    );
  }

  const documents = inventory?.documents ?? [];
  const statuses = documents.reduce<Record<string, number>>((acc, doc) => {
    acc[doc.current_status] = (acc[doc.current_status] ?? 0) + 1;
    return acc;
  }, {});
  const statusRows = Object.entries(statuses)
    .sort((a, b) => b[1] - a[1])
    .map(([status, count]) => ({
      stage: <span className="uppercase">{status}</span>,
      count,
    }));

  const healthy = health?.status === "ok" || health?.status === "healthy";

  return (
    <div className="mx-auto w-full max-w-screen-xl px-6 py-8 space-y-8">
      <header className="flex items-start justify-between">
        <div>
          <h1
            className="font-semibold mb-1"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            System Health
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            Service status and the document pipeline lifecycle
          </p>
        </div>
        <button
          onClick={() => load()}
          disabled={loading}
          className="btn btn-secondary"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </header>

      {error && <ErrorState message={error} onRetry={() => load()} />}

      {loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-64" />
        </>
      )}

      {!loading && !error && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              icon={Activity}
              value={health ? (healthy ? "Online" : health.status) : "Unknown"}
              label="API Status"
              hint={health ? health.service : "No response"}
              valueColor={
                healthy ? "var(--status-pass)" : "var(--color-text-primary)"
              }
              iconColor={
                healthy ? "var(--status-pass)" : "var(--color-text-tertiary)"
              }
            />
            <MetricCard
              icon={Server}
              value={health ? `v${health.version}` : "—"}
              label="Version"
              hint="Deployed build"
            />
            <MetricCard
              icon={Database}
              value={inventory?.count ?? documents.length}
              label="Documents"
              hint="Across all lifecycle stages"
            />
          </section>

          <section>
            <div className="card p-6">
              <header className="mb-6 flex items-center justify-between">
                <div>
                  <h2
                    className="font-semibold mb-1"
                    style={{
                      fontSize: "var(--font-size-lg)",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    Lifecycle Stages
                  </h2>
                  <p
                    style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    Document counts by pipeline stage
                  </p>
                </div>
                <Link
                  href="/"
                  className="btn btn-secondary text-xs"
                  style={{ padding: "var(--spacing-1) var(--spacing-3)" }}
                >
                  Classify / Upload
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </header>

              {statusRows.length === 0 ? (
                <EmptyState
                  icon={<Database className="h-8 w-8" />}
                  title="No documents in the pipeline"
                  message="Register and classify a document to see lifecycle stages populate."
                />
              ) : (
                <DataTable
                  label="Lifecycle stage counts"
                  columns={[
                    { key: "stage", header: "Stage" },
                    { key: "count", header: "Count", align: "right", mono: true },
                  ]}
                  rows={statusRows}
                />
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
