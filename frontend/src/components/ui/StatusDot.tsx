type StatusDotVariant = "online" | "offline" | "warning" | "error";

interface StatusDotProps {
  variant?: StatusDotVariant;
  label?: string;
  className?: string;
}

const VARIANT_STYLES: Record<StatusDotVariant, { color: string; animate: string }> = {
  online: {
    color: "bg-[var(--accent-emerald)]",
    animate: "animate-pulse-glow text-[var(--accent-emerald)]",
  },
  offline: {
    color: "bg-[var(--text-muted)]",
    animate: "",
  },
  warning: {
    color: "bg-[var(--accent-amber)]",
    animate: "animate-pulse-warning text-[var(--accent-amber)]",
  },
  error: {
    color: "bg-[var(--accent-red)]",
    animate: "animate-pulse-critical text-[var(--accent-red)]",
  },
};

export default function StatusDot({
  variant = "offline",
  label,
  className = "",
}: StatusDotProps) {
  const { color, animate } = VARIANT_STYLES[variant];

  return (
    <span className={`inline-flex items-center gap-2 ${className}`.trim()}>
      <span
        className={`inline-block h-2 w-2 rounded-full ${color} ${animate}`}
        aria-hidden="true"
      />
      {label && (
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      )}
    </span>
  );
}
