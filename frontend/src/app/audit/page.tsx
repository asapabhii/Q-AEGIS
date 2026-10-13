"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Link2 } from "lucide-react";

import NotPermitted from "@/components/ui/NotPermitted";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { listDocuments, ApiError } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";
import { ACCESS, roleAllowed } from "@/lib/auth/roles";

// This index route just resolves a document to inspect and forwards to
// /audit/[document_id]. Gate it on the AUDIT read set (not merely inventory):
// a role with inventory access but no audit access — e.g. CISO or Engineer —
// should see an honest 403 here immediately, not be redirected only to hit the
// gate on the destination page.
const AUDIT_ALLOWED = ACCESS.audit;

function AuditIndexResolver() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { role } = useRole();
  const permitted = roleAllowed(AUDIT_ALLOWED, role);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!permitted) {
      return;
    }
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    setEmpty(false);
    const requestedId = searchParams.get("document_id");
    if (requestedId) {
      // Honor a deep link straight to the requested document's audit trail.
      router.replace(`/audit/${encodeURIComponent(requestedId)}`);
      return;
    }
    listDocuments(role)
      .then((res) => {
        if (cancelled) return;
        if (res.documents.length > 0) {
          // Fall back to the first available document's audit trail.
          router.replace(`/audit/${res.documents[0].id}`);
        } else {
          setEmpty(true);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Network error");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role, permitted, router, searchParams, reloadKey]);

  if (!permitted) {
    return (
      <div className="mx-auto w-full max-w-screen-xl px-6 py-8">
        <NotPermitted
          role={role}
          allowed={AUDIT_ALLOWED}
          resource="The cryptographic audit trail"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-screen-xl space-y-8 px-6 py-8">
      <header>
        <div className="flex items-center gap-3 mb-1">
          <Link2 className="h-5 w-5" style={{ color: "var(--color-text-tertiary)" }} />
          <h1
            className="font-semibold"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            Cryptographic Audit Viewer
          </h1>
        </div>
        <p
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          Locating a document to inspect…
        </p>
      </header>

      {loading && <Skeleton className="h-40" />}

      {error && (
        <ErrorState
          message={error}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {empty && (
        <EmptyState
          icon={<Link2 className="h-8 w-8" />}
          title="No documents to inspect"
          message="No documents are registered in the system yet. Register and classify a document first — its audit trail will be available here."
        />
      )}
    </div>
  );
}

export default function AuditIndexPage() {
  return (
    <Suspense fallback={null}>
      <AuditIndexResolver />
    </Suspense>
  );
}
