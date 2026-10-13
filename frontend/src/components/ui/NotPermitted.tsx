"use client";

import { Lock } from "lucide-react";
import type { UserRole } from "@/lib/api/types";
import { ROLE_LABELS } from "@/lib/auth/roles";

/**
 * Honest "you can't do this" state for a page whose backend gate the current
 * caller role does not satisfy. This is a UX courtesy, NOT the security
 * boundary — the server enforces every gate regardless of what the UI shows.
 * Rendering this instead of firing a request that will 403 keeps the operator
 * oriented and never silently escalates a caller to a privileged role.
 */
export default function NotPermitted({
  role,
  allowed,
  resource = "this page",
}: {
  role: UserRole;
  allowed: readonly UserRole[];
  resource?: string;
}) {
  return (
    <div
      className="card p-8 flex flex-col items-center text-center gap-3"
      style={{ borderColor: "var(--color-border)" }}
    >
      <div
        className="flex h-12 w-12 items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--color-bg-tertiary)" }}
      >
        <Lock className="h-6 w-6" style={{ color: "var(--color-text-tertiary)" }} />
      </div>
      <h2
        className="font-semibold"
        style={{ fontSize: "var(--font-size-lg)", color: "var(--color-text-primary)" }}
      >
        Not permitted
      </h2>
      <p className="text-sm max-w-md" style={{ color: "var(--color-text-secondary)" }}>
        {resource} is available to{" "}
        {allowed.map((r) => ROLE_LABELS[r]).join(", ")}. You are acting as{" "}
        {ROLE_LABELS[role]}. Switch to an authorized role in the sidebar, or sign
        in with an account that has one.
      </p>
    </div>
  );
}
