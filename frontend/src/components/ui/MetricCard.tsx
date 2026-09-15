"use client";

import { useEffect, useState, useRef, type ReactNode } from "react";

type MetricTone = "teal" | "violet" | "emerald" | "amber" | "red" | "blue" | "cyan" | "neutral";

interface MetricCardProps {
  label: string;
  value: string | number;
  description?: string;
  icon?: ReactNode;
  tone?: MetricTone;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  animated?: boolean;
  className?: string;
}

const TONE_COLORS: Record<MetricTone, { border: string; glow: string; text: string; icon: string }> = {
  teal: {
    border: "rgba(20, 184, 166, 0.3)",
    glow: "0 0 30px -8px rgba(20, 184, 166, 0.4), 0 0 60px -12px rgba(20, 184, 166, 0.2)",
    text: "var(--quantum-teal)",
    icon: "bg-gradient-to-br from-teal-500/20 to-cyan-500/10",
  },
  cyan: {
    border: "rgba(6, 182, 212, 0.3)",
    glow: "0 0 30px -8px rgba(6, 182, 212, 0.4), 0 0 60px -12px rgba(6, 182, 212, 0.2)",
    text: "var(--quantum-cyan)",
    icon: "bg-gradient-to-br from-cyan-500/20 to-blue-500/10",
  },
  violet: {
    border: "rgba(139, 92, 246, 0.3)",
    glow: "0 0 30px -8px rgba(139, 92, 246, 0.4), 0 0 60px -12px rgba(139, 92, 246, 0.2)",
    text: "var(--quantum-violet)",
    icon: "bg-gradient-to-br from-violet-500/20 to-purple-500/10",
  },
  emerald: {
    border: "rgba(16, 185, 129, 0.3)",
    glow: "0 0 30px -8px rgba(16, 185, 129, 0.4), 0 0 60px -12px rgba(16, 185, 129, 0.2)",
    text: "var(--success)",
    icon: "bg-gradient-to-br from-emerald-500/20 to-green-500/10",
  },
  amber: {
    border: "rgba(245, 158, 11, 0.3)",
    glow: "0 0 30px -8px rgba(245, 158, 11, 0.4), 0 0 60px -12px rgba(245, 158, 11, 0.2)",
    text: "var(--warning)",
    icon: "bg-gradient-to-br from-amber-500/20 to-orange-500/10",
  },
  red: {
    border: "rgba(239, 68, 68, 0.3)",
    glow: "0 0 30px -8px rgba(239, 68, 68, 0.4), 0 0 60px -12px rgba(239, 68, 68, 0.2)",
    text: "var(--error)",
    icon: "bg-gradient-to-br from-red-500/20 to-rose-500/10",
  },
  blue: {
    border: "rgba(59, 130, 246, 0.3)",
    glow: "0 0 30px -8px rgba(59, 130, 246, 0.4), 0 0 60px -12px rgba(59, 130, 246, 0.2)",
    text: "var(--info)",
    icon: "bg-gradient-to-br from-blue-500/20 to-indigo-500/10",
  },
  neutral: {
    border: "rgba(139, 92, 246, 0.15)",
    glow: "0 4px 6px -1px rgba(0, 0, 0, 0.4)",
    text: "var(--base-100)",
    icon: "bg-gradient-to-br from-gray-500/10 to-slate-500/5",
  },
};

const TREND_ICONS: Record<"up" | "down" | "stable", { icon: string; color: string }> = {
  up: { icon: "↗", color: "text-emerald-400" },
  down: { icon: "↘", color: "text-red-400" },
  stable: { icon: "→", color: "text-gray-400" },
};

export default function MetricCard({
  label,
  value,
  description,
  icon,
  tone = "neutral",
  trend,
  trendValue,
  animated = true,
  className = "",
}: MetricCardProps) {
  const [displayValue, setDisplayValue] = useState<string | number>(animated && typeof value === "number" ? 0 : value);
  const [isHovered, setIsHovered] = useState(false);
  const hasAnimated = useRef(false);
  const colors = TONE_COLORS[tone];

  // Animate number count-up
  useEffect(() => {
    if (!animated || typeof value !== "number" || hasAnimated.current) {
      setDisplayValue(value);
      return;
    }

    hasAnimated.current = true;
    const duration = 1500;
    const steps = 60;
    const increment = value / steps;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      setDisplayValue((prev) => {
        const next = typeof prev === "number" ? prev + increment : increment;
        return currentStep >= steps ? value : Math.round(next);
      });

      if (currentStep >= steps) {
        clearInterval(timer);
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value, animated]);

  return (
    <div
      className={`group relative overflow-hidden rounded-xl bg-gradient-to-br from-[var(--base-850)] to-[var(--base-900)] p-6 transition-all duration-300 hover:scale-[1.02] ${className}`}
      style={{
        border: `1px solid ${colors.border}`,
        boxShadow: isHovered
          ? colors.glow
          : "0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Animated gradient border on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: `linear-gradient(135deg, ${colors.border} 0%, transparent 50%, ${colors.border} 100%)`,
          backgroundSize: "200% 200%",
          animation: "gradientFlow 3s ease infinite",
          maskImage: "linear-gradient(to bottom, transparent 0%, black 2px, black calc(100% - 2px), transparent 100%), linear-gradient(to right, transparent 0%, black 2px, black calc(100% - 2px), transparent 100%)",
          maskComposite: "intersect",
        }}
      />

      {/* Top accent gradient */}
      <div
        className="absolute inset-x-0 top-0 h-[2px] opacity-60"
        style={{
          background: `linear-gradient(90deg, ${colors.text} 0%, transparent 100%)`,
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex items-start justify-between">
        <div className="space-y-3 flex-1">
          {/* Label */}
          <div className="flex items-center gap-2">
            <p
              className="text-xs font-medium uppercase tracking-[0.1em] text-[var(--base-400)]"
              style={{ letterSpacing: "0.1em" }}
            >
              {label}
            </p>
            {trend && (
              <div className="flex items-center gap-1">
                <span className={`text-sm ${TREND_ICONS[trend].color}`}>
                  {TREND_ICONS[trend].icon}
                </span>
                {trendValue && (
                  <span className={`text-xs font-medium ${TREND_ICONS[trend].color}`}>
                    {trendValue}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Value */}
          <p
            className="font-display text-4xl font-bold tracking-tight transition-all duration-300"
            style={{
              color: colors.text,
              textShadow: isHovered ? `0 0 20px ${colors.text}40` : "none",
            }}
          >
            {displayValue}
          </p>

          {/* Description */}
          {description && (
            <p className="text-sm text-[var(--base-400)] leading-relaxed max-w-xs">
              {description}
            </p>
          )}
        </div>

        {/* Icon */}
        {icon && (
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${colors.icon} border transition-all duration-300 group-hover:scale-110`}
            style={{
              borderColor: colors.border,
              color: colors.text,
            }}
          >
            {icon}
          </div>
        )}
      </div>

      {/* Bottom glow effect */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px opacity-30"
        style={{
          background: `linear-gradient(90deg, transparent 0%, ${colors.text} 50%, transparent 100%)`,
        }}
      />
    </div>
  );
}
