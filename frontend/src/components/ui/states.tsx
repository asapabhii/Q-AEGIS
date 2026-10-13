"use client";

import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * A single grey block used to stand in for content while a request is in
 * flight. Compose several to sketch the shape of the page that is loading.
 */
export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`skeleton-pulse rounded-md ${className}`}
      style={{ backgroundColor: "var(--color-bg-tertiary)", ...style }}
      aria-hidden="true"
    />
  );
}

/**
 * Neutral "there is nothing here yet" state — distinct from an error. Used when
 * a request succeeded but returned no rows, so the operator knows the system is
 * working and simply empty rather than broken.
 */
export function EmptyState({
  icon,
  title,
  message,
  action,
}: {
  icon?: ReactNode;
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="card flex flex-col items-center justify-center gap-3 py-12 text-center"
      style={{ minHeight: "280px" }}
    >
      {icon && <div style={{ color: "var(--color-text-tertiary)" }}>{icon}</div>}
      <p
        className="text-base font-medium"
        style={{ color: "var(--color-text-primary)" }}
      >
        {title}
      </p>
      {message && (
        <p
          className="text-sm max-w-xs"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {message}
        </p>
      )}
      {action}
    </div>
  );
}

/**
 * Failure state for a request that errored. Shows the backend's message
 * verbatim (it is trusted data from our own API) and an optional retry action.
 */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="card p-6" style={{ borderColor: "var(--status-fail)" }}>
      <div className="flex items-center gap-3">
        <AlertTriangle
          className="h-5 w-5 flex-shrink-0"
          style={{ color: "var(--status-fail)" }}
        />
        <p className="text-sm flex-1" style={{ color: "var(--status-fail)" }}>
          {message}
        </p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn btn-secondary">
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
