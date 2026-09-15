import type { ReactNode } from "react";

export interface DataTableColumn {
  key: string;
  header: string;
  align?: "left" | "center" | "right";
  mono?: boolean;
  width?: string;
}

interface DataTableProps {
  label: string;
  columns: DataTableColumn[];
  rows: Array<Record<string, ReactNode>>;
  emptyMessage?: string;
  className?: string;
  onRowClick?: (index: number) => void;
}

const ALIGNMENTS = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
} as const;

export default function DataTable({
  label,
  columns,
  rows,
  emptyMessage = "No rows match the current filters.",
  className = "",
  onRowClick,
}: DataTableProps) {
  return (
    <div className={`table-container ${className}`.trim()}>
      <table className="w-full border-collapse">
        <caption className="sr-only">{label}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={`table-header table-cell ${ALIGNMENTS[column.align ?? "left"]}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length > 0 ? (
            rows.map((row, rowIndex) => (
              <tr
                key={`row-${rowIndex}`}
                onClick={onRowClick ? () => onRowClick(rowIndex) : undefined}
                className={`table-row ${onRowClick ? "cursor-pointer" : ""}`}
              >
                {columns.map((column) => (
                  <td
                    key={`${column.key}-${rowIndex}`}
                    className={`table-cell align-top ${ALIGNMENTS[column.align ?? "left"]} ${column.mono ? "mono-data text-xs" : "text-sm text-[var(--color-text-primary)]"}`}
                  >
                    {row[column.key]}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-10 text-center text-sm"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                {emptyMessage}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
