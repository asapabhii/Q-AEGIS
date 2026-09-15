"use client";

import { useState } from "react";
import { Shield, Lock, Zap } from "lucide-react";

export type EncryptionTier = "aes256" | "hybrid" | "post_quantum";

interface EncryptionTierBarProps {
  currentTier: EncryptionTier;
  trustScore: number;
  showUpgradeRecommendation?: boolean;
  className?: string;
}

const TIER_CONFIG = {
  aes256: {
    label: "AES-256",
    level: 1,
    color: "#8B5CF6",
    description: "Classical symmetric encryption",
    technical: "AES-256-GCM, 256-bit key",
    icon: Lock,
  },
  hybrid: {
    label: "Hybrid PQC",
    level: 2,
    color: "#A855F7",
    description: "Classical + Post-Quantum",
    technical: "X25519 + ML-KEM-768",
    icon: Shield,
  },
  post_quantum: {
    label: "Full Post-Quantum",
    level: 3,
    color: "#06B6D4",
    description: "Quantum-resistant",
    technical: "ML-KEM-1024 + ML-DSA-87",
    icon: Zap,
  },
};

export default function EncryptionTierBar({
  currentTier,
  trustScore,
  showUpgradeRecommendation = false,
  className = "",
}: EncryptionTierBarProps) {
  const [hoveredTier, setHoveredTier] = useState<EncryptionTier | null>(null);
  const currentConfig = TIER_CONFIG[currentTier];
  const CurrentIcon = currentConfig.icon;

  // Calculate recommended tier based on trust score
  const getRecommendedTier = (): EncryptionTier => {
    if (trustScore >= 80) return "post_quantum";
    if (trustScore >= 50) return "hybrid";
    return "aes256";
  };

  const recommendedTier = getRecommendedTier();
  const shouldUpgrade = TIER_CONFIG[recommendedTier].level > currentConfig.level;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Current Tier Display */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--base-500)] mb-1">Current Protection</p>
          <div className="flex items-center gap-2">
            <CurrentIcon className="h-5 w-5" style={{ color: currentConfig.color }} />
            <span
              className="text-lg font-semibold font-display"
              style={{ color: currentConfig.color }}
            >
              {currentConfig.label}
            </span>
          </div>
          <p className="text-xs text-[var(--base-400)] mt-0.5">
            {currentConfig.description}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--base-500)] mb-1">Level</p>
          <p className="text-3xl font-bold gradient-text">{currentConfig.level}</p>
          <p className="text-xs text-[var(--base-500)]">of 3</p>
        </div>
      </div>

      {/* Tier Progress Bar */}
      <div className="relative">
        {/* Track */}
        <div className="h-3 bg-[var(--base-800)] rounded-full overflow-hidden relative">
          {/* Fill - gradient based on current tier */}
          <div
            className="h-full rounded-full transition-all duration-700 relative overflow-hidden"
            style={{
              width: `${(currentConfig.level / 3) * 100}%`,
              background: `linear-gradient(90deg, ${TIER_CONFIG.aes256.color}, ${TIER_CONFIG.hybrid.color}, ${TIER_CONFIG.post_quantum.color})`,
            }}
          >
            {/* Animated shimmer */}
            <div
              className="absolute inset-0 opacity-50"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)",
                backgroundSize: "200% 100%",
                animation: "shimmer 2s infinite linear",
              }}
            />
          </div>

          {/* Tier markers */}
          <div className="absolute inset-0 flex items-center justify-between px-1">
            {(["aes256", "hybrid", "post_quantum"] as EncryptionTier[]).map(
              (tier, idx) => {
                const config = TIER_CONFIG[tier];
                const isActive = config.level <= currentConfig.level;
                const Icon = config.icon;
                return (
                  <div
                    key={tier}
                    className="relative"
                    style={{ left: `${(idx / 2) * 100}%` }}
                  >
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all ${
                        isActive
                          ? "bg-[var(--base-900)] border-white scale-110"
                          : "bg-[var(--base-700)] border-[var(--base-600)]"
                      }`}
                      onMouseEnter={() => setHoveredTier(tier)}
                      onMouseLeave={() => setHoveredTier(null)}
                    >
                      <Icon
                        className="h-3 w-3"
                        style={{ color: isActive ? config.color : "#556382" }}
                      />
                    </div>
                  </div>
                );
              }
            )}
          </div>
        </div>

        {/* Labels under bar */}
        <div className="flex justify-between mt-2 px-1">
          {(["aes256", "hybrid", "post_quantum"] as EncryptionTier[]).map((tier) => {
            const config = TIER_CONFIG[tier];
            const isActive = tier === currentTier;
            return (
              <div
                key={tier}
                className={`text-center transition-all ${
                  isActive ? "opacity-100" : "opacity-40"
                }`}
              >
                <p
                  className="text-[10px] font-medium"
                  style={{ color: isActive ? config.color : "#556382" }}
                >
                  {config.label}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tier Details */}
      {hoveredTier && (
        <div className="animate-slide-down glass-elevated rounded-lg p-4 border border-violet-500/30">
          <div className="flex items-center gap-2 mb-2">
            {(() => {
              const Icon = TIER_CONFIG[hoveredTier].icon;
              return (
                <Icon
                  className="h-5 w-5"
                  style={{ color: TIER_CONFIG[hoveredTier].color }}
                />
              );
            })()}
            <span className="text-sm font-semibold text-[var(--base-100)]">
              {TIER_CONFIG[hoveredTier].label}
            </span>
          </div>
          <p className="text-xs text-[var(--base-400)] mb-2">
            {TIER_CONFIG[hoveredTier].description}
          </p>
          <p className="text-xs mono-data text-[var(--base-500)]">
            {TIER_CONFIG[hoveredTier].technical}
          </p>
        </div>
      )}

      {/* Technical Details */}
      <div className="glass-subtle rounded-lg p-4 space-y-2">
        <p className="text-xs text-[var(--base-500)] uppercase tracking-wider">
          Technical Specification
        </p>
        <p className="text-sm mono-data text-[var(--base-300)]">
          {currentConfig.technical}
        </p>
        {currentTier === "hybrid" && (
          <p className="text-xs text-[var(--base-500)] leading-relaxed">
            Combines classical X25519 ECDH with post-quantum ML-KEM-768. Security
            holds even if one algorithm is broken.
          </p>
        )}
        {currentTier === "post_quantum" && (
          <p className="text-xs text-[var(--base-500)] leading-relaxed">
            NIST Level 5 security. Resistant to Shor&apos;s algorithm and other quantum
            attacks. ML-DSA-87 for digital signatures.
          </p>
        )}
      </div>

      {/* Upgrade Recommendation */}
      {showUpgradeRecommendation && shouldUpgrade && (
        <div className="glass-elevated rounded-lg p-4 border border-cyan-500/30 glow-cyan animate-slide-up">
          <div className="flex items-start gap-3">
            <Zap className="h-5 w-5 text-cyan-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-cyan-400 mb-1">
                Upgrade Available
              </p>
              <p className="text-xs text-[var(--base-400)] leading-relaxed mb-3">
                Based on trust score of {trustScore}, we recommend upgrading to{" "}
                <span className="font-semibold text-[var(--base-200)]">
                  {TIER_CONFIG[recommendedTier].label}
                </span>{" "}
                for enhanced quantum-resistant protection.
              </p>
              <button className="px-4 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-sm font-medium text-cyan-400 hover:bg-cyan-500/20 transition-all group">
                Request Upgrade
                <span className="inline-block ml-2 transition-transform group-hover:translate-x-1">
                  →
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
