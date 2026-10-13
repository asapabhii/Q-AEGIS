"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ShieldCheck,
  FileText,
  Lock,
  Cpu,
  ArrowUpRight,
} from "lucide-react";

import Badge from "@/components/ui/Badge";
import DataTable from "@/components/ui/DataTable";
import MetricCard from "@/components/ui/MetricCard";
import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { ApiError, listDocuments } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import { cryptoLabel, cryptoTone } from "@/lib/crypto-labels";
import { countLabeled } from "@/lib/inventory";
import type {
  DocumentInventoryResponse,
  DocumentSnapshot,
  SensitivityLabel,
} from "@/lib/api/types";

const LABEL_TONES: Record<
  SensitivityLabel,
  "public" | "internal" | "confidential" | "restricted"
> = {
  PUBLIC: "public",
  INTERNAL: "internal",
  CONFIDENTIAL: "confidential",
  RESTRICTED: "restricted",
};

function dash() {
  return <span style={{ color: "var(--color-text-tertiary)" }}>—</span>;
}

const FLEET_ALLOWED = ACCESS.ciso;

export default function CisoPage() {
  const router = useRouter();
  const { role } = useRole();
  // The fleet inventory read is gated server-side; send the caller's real role
  // and render an honest 403 rather than defaulting anyone to "ciso".
  const permitted = roleAllowed(FLEET_ALLOWED, role);
  const [inventory, setInventory] = useState<DocumentInventoryResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!permitted) {
      return;
    }
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    listDocuments(role)
      .then((res) => {
        if (cancelled) return;
        setInventory(res);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setInventory(null);
        setError(err instanceof ApiError ? err.message : "Network error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role, permitted]);

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={FLEET_ALLOWED}
          resource="The fleet posture view"
        />
      </div>
    );
  }

  const documents = inventory?.documents ?? [];
  const labeled = countLabeled(documents);
  const protectedCount = documents.filter(
    (d) => d.current_status === "protected"
  ).length;
  const pq = documents.filter((d) => d.profile_type === "post_quantum").length;
  const hybrid = documents.filter((d) => d.profile_type === "hybrid").length;

  const rows = documents.map((doc: DocumentSnapshot) => {
    const trust = doc.trust_score !== null ? Number(doc.trust_score) : null;
    return {
      filename: (
        <span style={{ color: "var(--color-text-primary)" }}>{doc.filename}</span>
      ),
      label: doc.sensitivity_label ? (
        <Badge
          label={doc.sensitivity_label}
          tone={LABEL_TONES[doc.sensitivity_label]}
          size="sm"
        />
      ) : (
        dash()
      ),
      trust:
        trust !== null && Number.isFinite(trust) ? trust.toFixed(1) : dash(),
      policy: doc.final_decision ? (
        <span className="uppercase">{doc.final_decision}</span>
      ) : (
        dash()
      ),
      profile: doc.profile_type ? (
        <Badge
          label={cryptoLabel(doc.profile_type)}
          tone={cryptoTone(doc.profile_type)}
          size="sm"
        />
      ) : (
        dash()
      ),
      links: (
        <div className="flex items-center gap-3 whitespace-nowrap">
          <Link
            href={`/documents/${doc.id}/summary`}
            className="text-xs hover:underline"
            style={{ color: "var(--color-accent)" }}
            onClick={(e) => e.stopPropagation()}
          >
            Summary
          </Link>
          <Link
            href={`/agents?document_id=${doc.id}`}
            className="text-xs hover:underline"
            style={{ color: "var(--color-accent)" }}
            onClick={(e) => e.stopPropagation()}
          >
            Agents
          </Link>
          <Link
            href={`/audit/${doc.id}`}
            className="text-xs hover:underline"
            style={{ color: "var(--color-accent)" }}
            onClick={(e) => e.stopPropagation()}
          >
            Audit
          </Link>
        </div>
      ),
    };
  });

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
          Fleet Posture
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Executive summary of classification coverage and cryptographic protection
        </p>
      </header>

      {error && <ErrorState message={error} />}

      {loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-80" />
        </>
      )}

      {!loading && !error && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              icon={FileText}
              value={inventory?.count ?? documents.length}
              label="Documents"
              hint="Registered in inventory"
            />
            <MetricCard
              icon={ShieldCheck}
              value={labeled}
              label="Labeled"
              hint="Classification complete"
            />
            <MetricCard
              icon={Lock}
              value={protectedCount}
              label="Protected"
              hint="Encryption applied"
            />
            <MetricCard
              icon={Cpu}
              value={`${pq} / ${hybrid}`}
              label="PQ / Hybrid"
              hint="Quantum-ready profiles"
              iconColor="var(--crypto-pqc)"
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
                    Document Fleet
                  </h2>
                  <p
                    style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    Every registered document with its label, trust, policy, and profile
                  </p>
                </div>
                <Link
                  href="/dashboard"
                  className="btn btn-secondary text-xs"
                  style={{ padding: "var(--spacing-1) var(--spacing-3)" }}
                >
                  Risk Dashboard
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </header>

              {documents.length === 0 ? (
                <EmptyState
                  icon={<FileText className="h-8 w-8" />}
                  title="No documents registered"
                  message="Once documents are uploaded and classified they appear here with full posture detail."
                />
              ) : (
                <DataTable
                  label="Document fleet posture"
                  columns={[
                    { key: "filename", header: "Filename" },
                    { key: "label", header: "Label" },
                    { key: "trust", header: "Trust", align: "right", mono: true },
                    { key: "policy", header: "Policy", mono: true },
                    { key: "profile", header: "Profile" },
                    { key: "links", header: "Deep dive" },
                  ]}
                  rows={rows}
                  onRowClick={(i) =>
                    router.push(`/documents/${documents[i].id}/summary`)
                  }
                />
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
