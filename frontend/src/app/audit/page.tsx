"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, ShieldAlert } from "lucide-react";

import { listDocuments, ApiError } from "@/lib/api/client";
import { useRole } from "@/lib/context/RoleContext";

export default function AuditIndexPage() {
  const router = useRouter();
  const { role } = useRole();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDocuments(role)
      .then((res) => {
        if (cancelled) return;
        if (res.documents.length > 0) {
          // Redirect to the first available document's audit trail
          router.replace(`/audit/${res.documents[0].id}`);
        } else {
          setError("No documents found in the system. Please register a document first.");
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
  }, [role, router]);

  return (
    <div className="mx-auto w-full max-w-screen-xl space-y-8 px-6 py-8">
      <header data-reveal>
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
          Locating a valid document to inspect...
        </p>
      </header>

      {loading && (
        <div className="flex items-center justify-center min-h-[200px]">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Searching for documents...
          </p>
        </div>
      )}

      {error && (
        <div className="card p-6" style={{ borderColor: "var(--status-fail)" }}>
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5" style={{ color: "var(--status-fail)" }} />
            <p className="text-sm" style={{ color: "var(--status-fail)" }}>
              {error}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
