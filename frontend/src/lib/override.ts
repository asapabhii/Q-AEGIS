import type { SensitivityLabel } from "@/lib/api/types";

/** Matches ``manual_overrides.justification`` and ``PRD.md`` FR-12. */
export const MIN_JUSTIFICATION_CHARS = 20;

export const SENSITIVITY_LABELS: readonly SensitivityLabel[] = [
  "PUBLIC",
  "INTERNAL",
  "CONFIDENTIAL",
  "RESTRICTED",
];

export function strippedJustificationLength(value: string): number {
  return value.trim().length;
}

export function canSubmitOverride(options: {
  documentId: string;
  hasClassifiedSnapshot: boolean;
  newLabel: SensitivityLabel | "";
  currentLabel: SensitivityLabel | null;
  justification: string;
  confirmed: boolean;
  loading: boolean;
}): boolean {
  if (options.loading) return false;
  if (!options.documentId.trim()) return false;
  if (!options.hasClassifiedSnapshot) return false;
  if (!options.newLabel) return false;
  if (options.newLabel === options.currentLabel) return false;
  if (strippedJustificationLength(options.justification) < MIN_JUSTIFICATION_CHARS) {
    return false;
  }
  return options.confirmed;
}
