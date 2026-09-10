import type { SensitivityLabel } from "@/lib/api/types";

const LABEL_STYLES: Record<SensitivityLabel, string> = {
  PUBLIC: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  INTERNAL: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  CONFIDENTIAL: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  RESTRICTED: "bg-red-500/15 text-red-400 border-red-500/30",
};

export function LabelBadge({ label }: { label: SensitivityLabel }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${LABEL_STYLES[label]}`}
    >
      {label}
    </span>
  );
}
