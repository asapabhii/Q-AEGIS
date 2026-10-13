"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Anchor,
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Link2,
} from "lucide-react";

import HashDisplay from "@/components/ui/HashDisplay";
import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  ApiError,
  getSigningKey,
  issueCheckpoint,
  listCheckpoints,
  verifyCheckpoint,
} from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";
import type {
  CheckpointVerificationResponse,
  SignedCheckpointResponse,
  SigningKeyResponse,
} from "@/lib/api/types";

const READ_ALLOWED = ACCESS.audit;

function CheckpointsInner() {
  const params = useSearchParams();
  const { role } = useRole();
  const permitted = roleAllowed(READ_ALLOWED, role);
  const canIssue = roleAllowed(ACCESS.checkpointIssue, role);
  const queryId = params.get("document_id") ?? "";

  const [documentId, setDocumentId] = useState(queryId);
  const [chainId, setChainId] = useState<string | null>(
    queryId.trim() || null
  );
  const [checkpoints, setCheckpoints] = useState<SignedCheckpointResponse[]>([]);
  const [signingKey, setSigningKey] = useState<SigningKeyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [verifications, setVerifications] = useState<
    Record<string, CheckpointVerificationResponse | "pending" | { error: string }>
  >({});

  const load = useCallback(
    (id: string | null) => {
      if (!permitted) return () => {};
      let cancelled = false;
      setLoading(true);
      setError(null);
      setVerifications({});
      Promise.all([
        listCheckpoints(id, role),
        getSigningKey(role).catch((err: unknown) => {
          // 404 until the first checkpoint is ever issued — not an error.
          if (err instanceof ApiError && err.status === 404) return null;
          throw err;
        }),
      ])
        .then(([list, key]) => {
          if (cancelled) return;
          setCheckpoints(list);
          setSigningKey(key);
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
    },
    [permitted, role]
  );

  useEffect(() => load(chainId), [load, chainId]);

  async function handleIssue() {
    if (!canIssue || issuing) return;
    setIssuing(true);
    setIssueError(null);
    try {
      await issueCheckpoint(
        { document_id: chainId ?? null },
        role
      );
      load(chainId);
    } catch (err) {
      setIssueError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setIssuing(false);
    }
  }

  async function handleVerify(id: string) {
    setVerifications((prev) => ({ ...prev, [id]: "pending" }));
    try {
      const result = await verifyCheckpoint(id, role);
      setVerifications((prev) => ({ ...prev, [id]: result }));
    } catch (err) {
      setVerifications((prev) => ({
        ...prev,
        [id]: { error: err instanceof ApiError ? err.message : "Network error" },
      }));
    }
  }

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={READ_ALLOWED}
          resource="Audit checkpoints"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-screen-xl px-6 py-8 space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Anchor className="h-5 w-5" style={{ color: "var(--color-text-tertiary)" }} />
            <h1
              className="font-semibold"
              style={{
                fontSize: "var(--font-size-2xl)",
                color: "var(--color-text-primary)",
              }}
            >
              Audit Checkpoints
            </h1>
          </div>
          <p
            className="max-w-2xl"
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            Post-quantum Signed Tree Heads (ML-DSA-87) anchoring the append-only
            Merkle audit chain. Each checkpoint signs (chain, tree size, root,
            timestamp) so a party who does not trust the operator can prove the
            log was never rewritten after anchoring.
          </p>
        </div>
        <Link href="/audit" className="btn btn-secondary">
          <Link2 className="h-4 w-4" />
          Audit Trail
        </Link>
      </header>

      {/* Chain selector + issue */}
      <div className="card p-4 space-y-3">
        <label
          htmlFor="checkpoint-document-id"
          className="block text-xs uppercase tracking-wider"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          Chain — document ID, or empty for the system chain
        </label>
        <div className="flex flex-wrap gap-2">
          <input
            id="checkpoint-document-id"
            type="text"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setChainId(documentId.trim() || null);
            }}
            className="input mono-data flex-1 min-w-[240px]"
            placeholder="Leave blank for the system-wide chain..."
          />
          <button
            type="button"
            onClick={() => setChainId(documentId.trim() || null)}
            disabled={loading}
            className="btn btn-secondary"
          >
            Load
          </button>
          {canIssue && (
            <button
              type="button"
              onClick={() => void handleIssue()}
              disabled={issuing || loading}
              className="btn btn-primary"
            >
              <Anchor className="h-4 w-4" />
              {issuing ? "Anchoring…" : "Issue checkpoint"}
            </button>
          )}
        </div>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          {chainId
            ? `Viewing the chain for document ${chainId}.`
            : "Viewing the system-wide audit chain."}
          {!canIssue &&
            " Issuing a checkpoint requires the Auditor or Security Admin role."}
        </p>
        {issueError && (
          <p className="text-sm" style={{ color: "var(--status-fail)" }}>
            {issueError}
          </p>
        )}
      </div>

      {/* Signing key */}
      {signingKey && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <KeyRound className="h-4 w-4" style={{ color: "var(--crypto-pqc)" }} />
            <h2
              className="text-sm font-semibold"
              style={{ color: "var(--color-text-primary)" }}
            >
              Active signing key
            </h2>
          </div>
          <p className="text-xs mb-4" style={{ color: "var(--color-text-tertiary)" }}>
            Pin this public key out-of-band. Verification checks each signature
            against the key it was signed under, so a rotated or substituted key
            cannot forge a valid checkpoint.
          </p>
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt style={{ color: "var(--color-text-tertiary)" }}>Algorithm</dt>
              <dd className="mono-data" style={{ color: "var(--crypto-pqc)" }}>
                {signingKey.algorithm}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt style={{ color: "var(--color-text-tertiary)" }}>Key ID</dt>
              <dd>
                <HashDisplay hash={signingKey.signing_key_id} />
              </dd>
            </div>
            <div className="flex justify-between gap-3 sm:col-span-2">
              <dt style={{ color: "var(--color-text-tertiary)" }}>Public key</dt>
              <dd className="min-w-0">
                <HashDisplay hash={signingKey.public_key} />
              </dd>
            </div>
          </dl>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => load(chainId)} />}

      {loading && (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      )}

      {!loading && !error && checkpoints.length === 0 && (
        <EmptyState
          icon={<Anchor className="h-8 w-8" />}
          title="No checkpoints anchored yet"
          message={
            canIssue
              ? "Issue the first checkpoint to sign this chain's current Merkle root."
              : "No Signed Tree Head has been issued for this chain. An auditor can anchor one."
          }
        />
      )}

      {!loading && !error && checkpoints.length > 0 && (
        <div className="space-y-4">
          {checkpoints.map((cp) => {
            const v = verifications[cp.checkpoint_id];
            return (
              <div key={cp.checkpoint_id} className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div>
                    <p
                      className="text-sm font-semibold"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      Tree size {cp.tree_size}
                    </p>
                    <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                      Signed {new Date(cp.signed_at).toLocaleString()} ·{" "}
                      <span className="mono-data">{cp.algorithm}</span>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleVerify(cp.checkpoint_id)}
                    disabled={v === "pending"}
                    className="btn btn-secondary"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    {v === "pending" ? "Verifying…" : "Verify"}
                  </button>
                </div>

                <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2 text-sm mb-1">
                  <div className="flex justify-between gap-3">
                    <dt style={{ color: "var(--color-text-tertiary)" }}>Merkle root</dt>
                    <dd>
                      <HashDisplay hash={cp.merkle_root} />
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt style={{ color: "var(--color-text-tertiary)" }}>Signature</dt>
                    <dd>
                      <HashDisplay hash={cp.signature} />
                    </dd>
                  </div>
                </dl>

                {v && v !== "pending" && <VerifyResult result={v} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function CheckpointsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
          <Skeleton className="h-64" />
        </div>
      }
    >
      <CheckpointsInner />
    </Suspense>
  );
}

/**
 * Renders the outcome of an independent checkpoint re-check. A valid signature
 * over a root that no longer matches the recomputed prefix root is the tamper
 * signal — the log was rewritten after it was anchored.
 */
function VerifyResult({
  result,
}: {
  result: CheckpointVerificationResponse | { error: string };
}) {
  if ("error" in result) {
    return (
      <div
        className="mt-3 rounded-lg px-3 py-2 text-sm"
        style={{
          backgroundColor: "var(--color-bg-tertiary)",
          color: "var(--status-fail)",
        }}
      >
        {result.error}
      </div>
    );
  }

  const ok = result.is_valid;
  const tone = ok ? "var(--status-pass)" : "var(--status-fail)";

  return (
    <div
      className="mt-3 rounded-lg p-3 space-y-2"
      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
    >
      <div className="flex items-center gap-2">
        {ok ? (
          <ShieldCheck className="h-4 w-4" style={{ color: tone }} />
        ) : (
          <ShieldAlert className="h-4 w-4" style={{ color: tone }} />
        )}
        <span className="text-sm font-semibold" style={{ color: tone }}>
          {ok ? "Checkpoint valid" : "Tamper detected"}
        </span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
        <span style={{ color: "var(--color-text-secondary)" }}>
          Signature:{" "}
          <span
            style={{
              color: result.signature_valid
                ? "var(--status-pass)"
                : "var(--status-fail)",
            }}
          >
            {result.signature_valid ? "valid" : "invalid"}
          </span>
        </span>
        <span style={{ color: "var(--color-text-secondary)" }}>
          Root match:{" "}
          <span
            style={{
              color: result.root_matches
                ? "var(--status-pass)"
                : "var(--status-fail)",
            }}
          >
            {result.root_matches ? "yes" : "no"}
          </span>
        </span>
      </div>
      {!result.root_matches && (
        <dl className="space-y-1 text-xs mono-data pt-1">
          <div className="flex justify-between gap-3">
            <dt style={{ color: "var(--color-text-tertiary)" }}>Stored root</dt>
            <dd>
              <HashDisplay hash={result.stored_root} />
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt style={{ color: "var(--color-text-tertiary)" }}>Recomputed</dt>
            <dd>
              <HashDisplay hash={result.recomputed_root} />
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}
