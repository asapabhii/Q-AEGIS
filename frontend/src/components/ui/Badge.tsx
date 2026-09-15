import type { CSSProperties } from "react";

export type BadgeTone =
  | "pass"
  | "fail"
  | "override"
  | "pending"
  | "info"
  | "public"
  | "internal"
  | "confidential"
  | "restricted"
  | "aes"
  | "hybrid"
  | "pqc";

export type BadgeSize = "sm" | "md" | "lg";

const TONE_VARIABLES: Record<string, string> = {
  pass: "--status-pass",
  fail: "--status-fail",
  override: "--status-override",
  pending: "--status-pending",
  info: "--status-info",
  aes: "--crypto-aes",
  hybrid: "--crypto-hybrid",
  pqc: "--crypto-pqc",
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: "px-1.5 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
  lg: "px-3.5 py-1.5 text-sm",
};

interface BadgeProps {
  label: string;
  tone: BadgeTone;
  size?: BadgeSize;
  live?: boolean;
  className?: string;
}

export default function Badge({
  label,
  tone,
  size = "md",
  live = false,
  className = "",
}: BadgeProps) {
  const isLabelTone = ["public", "internal", "confidential", "restricted"].includes(tone);

  if (isLabelTone) {
    return (
      <span
        className={`badge badge-${tone} ${SIZE_CLASSES[size]} ${className}`.trim()}
      >
        {live && (
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 rounded-full animate-pulse mr-1.5"
            style={{ backgroundColor: "currentColor" }}
          />
        )}
        {label}
      </span>
    );
  }

  const color = `var(${TONE_VARIABLES[tone]})`;
  const style: CSSProperties = {
    color,
    borderColor: `color-mix(in srgb, ${color} 30%, transparent)`,
    backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
  };

  return (
    <span
      style={style}
      className={`badge ${SIZE_CLASSES[size]} ${className}`.trim()}
    >
      {live && (
        <span
          aria-hidden="true"
          className="inline-block h-1.5 w-1.5 rounded-full animate-pulse mr-1.5"
          style={{ backgroundColor: color }}
        />
      )}
      {label}
    </span>
  );
}
