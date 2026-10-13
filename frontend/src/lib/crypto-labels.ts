import type { CryptoProfileType } from "@/lib/api/types";

/** Badge tone key shared by every surface that shows a crypto profile. */
export type CryptoTone = "aes" | "hybrid" | "pqc";

interface CryptoProfileMeta {
  /** Compact label for dense tables and fleet tiles. */
  short: string;
  /** Fuller label naming the concrete primitive, for detail views. */
  full: string;
  /** Badge tone. */
  tone: CryptoTone;
}

/**
 * Single source of truth for how each crypto profile is labelled and toned in
 * the UI. The dashboard, the CISO fleet view, and the document summary each
 * used to re-declare their own PROFILE_LABELS/PROFILE_TONES, which had already
 * drifted for the same `profile_type` ("PQC" vs "Full PQC", "Hybrid" vs
 * "Hybrid X25519MLKEM768"). Centralising them here keeps the compact and
 * detailed spellings deliberate variants of one source rather than three copies
 * free to diverge. The primitive names mirror the backend crypto-agile profiles
 * (AES-256-GCM / X25519MLKEM768 / ML-KEM-1024 + ML-DSA-87).
 */
export const CRYPTO_PROFILE_META: Record<CryptoProfileType, CryptoProfileMeta> = {
  aes256: { short: "AES-256", full: "AES-256", tone: "aes" },
  hybrid: { short: "Hybrid", full: "Hybrid X25519MLKEM768", tone: "hybrid" },
  post_quantum: { short: "PQC", full: "Full PQC", tone: "pqc" },
};

/** Profile label; `short` for tiles/tables (default), `full` for detail views. */
export function cryptoLabel(
  profile: CryptoProfileType,
  variant: "short" | "full" = "short",
): string {
  return CRYPTO_PROFILE_META[profile][variant];
}

/** Badge tone for a crypto profile. */
export function cryptoTone(profile: CryptoProfileType): CryptoTone {
  return CRYPTO_PROFILE_META[profile].tone;
}
