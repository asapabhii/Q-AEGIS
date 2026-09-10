import type { DocumentSnapshot } from "@/lib/api/types";

/** Null stages stay a dash. The API does not invent a label, score, or profile. */
export function displayStage(value: string | null): string {
  return value === null ? "—" : value;
}

export function countLabeled(documents: DocumentSnapshot[]): number {
  return documents.filter((row) => row.sensitivity_label !== null).length;
}
