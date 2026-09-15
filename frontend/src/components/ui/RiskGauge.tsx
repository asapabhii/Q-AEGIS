"use client";

import { useEffect, useRef } from "react";

interface RiskGaugeProps {
  /** Value between 0 and 1 */
  value: number;
  /** Label shown below the value */
  label?: string;
  /** Gauge diameter in pixels */
  size?: number;
  /** Stroke width */
  strokeWidth?: number;
  className?: string;
}

function valueToColor(value: number): string {
  if (value >= 0.7) return "var(--accent-red)";
  if (value >= 0.4) return "var(--accent-amber)";
  return "var(--accent-emerald)";
}

function invertedValueToColor(value: number): string {
  // For trust scores where higher = better
  if (value >= 0.7) return "var(--accent-emerald)";
  if (value >= 0.4) return "var(--accent-amber)";
  return "var(--accent-red)";
}

export default function RiskGauge({
  value,
  label,
  size = 120,
  strokeWidth = 8,
  className = "",
}: RiskGaugeProps) {
  const pathRef = useRef<SVGCircleElement>(null);
  const clampedValue = Math.max(0, Math.min(1, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75; // 270 degrees
  const fillLength = arcLength * clampedValue;
  const color = label?.toLowerCase().includes("trust")
    ? invertedValueToColor(clampedValue)
    : valueToColor(clampedValue);

  useEffect(() => {
    const path = pathRef.current;
    if (!path) return;

    // Animate on mount
    const targetOffset = arcLength - fillLength;
    path.style.transition = "stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1)";
    path.style.strokeDashoffset = `${targetOffset}`;
  }, [arcLength, fillLength]);

  const center = size / 2;
  const rotation = 135; // Start from bottom-left

  return (
    <div className={`inline-flex flex-col items-center gap-2 ${className}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="transform"
        >
          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--surface-3)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${arcLength} ${circumference}`}
            transform={`rotate(${rotation} ${center} ${center})`}
          />
          {/* Value arc */}
          <circle
            ref={pathRef}
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={arcLength}
            transform={`rotate(${rotation} ${center} ${center})`}
            style={{
              filter: `drop-shadow(0 0 6px ${color})`,
            }}
          />
        </svg>
        {/* Center value */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="mono-data text-2xl font-bold"
            style={{ color }}
          >
            {(clampedValue * 100).toFixed(0)}
          </span>
          <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
            / 100
          </span>
        </div>
      </div>
      {label && (
        <span className="text-xs font-medium text-[var(--text-secondary)]">
          {label}
        </span>
      )}
    </div>
  );
}
