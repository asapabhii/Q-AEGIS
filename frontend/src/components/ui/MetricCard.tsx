"use client";

import type { ComponentType, ReactNode } from "react";

/**
 * A single top-of-page metric: an icon, a big value, a label, and an optional
 * one-line hint. Consolidates the near-identical metric cards that were
 * hand-rolled on the dashboard, CISO, and engineer pages so every surface
 * reads the same.
 */
export default function MetricCard({
  icon: Icon,
  value,
  label,
  hint,
  valueColor = "var(--color-text-primary)",
  iconColor = "var(--color-text-tertiary)",
}: {
  icon: ComponentType<{ className?: string; style?: React.CSSProperties }>;
  value: ReactNode;
  label: string;
  hint?: ReactNode;
  valueColor?: string;
  iconColor?: string;
}) {
  return (
    <div className="card card-hover p-4">
      <div className="flex items-start justify-between mb-2">
        <Icon className="h-4 w-4" style={{ color: iconColor }} />
        <span
          className="mono-data text-2xl font-semibold"
          style={{ color: valueColor }}
        >
          {value}
        </span>
      </div>
      <div
        className="text-xs uppercase tracking-wider mb-1"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {label}
      </div>
      {hint && (
        <div className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}
