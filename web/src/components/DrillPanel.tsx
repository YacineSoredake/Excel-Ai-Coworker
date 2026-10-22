"use client";

import { fmtNum } from "@/lib/chartOption";
import type { Row } from "@/lib/dataEngine";

const cell = (v: unknown): string => {
  if (v == null) return "–";
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (typeof v === "number") return fmtNum(v);
  return String(v);
};

/** The rows behind a bar, point or month, with their Excel row numbers (report §5: inspect the underlying rows). */
export default function DrillPanel({ title, rows, measure, currency, onClose, onFilter }: {
  title: string; rows: Row[]; measure: string | null; currency: string | null; onClose: () => void; onFilter?: () => void;
}) {
  const shown = rows.slice(0, 100);
  const cols = rows.length ? Object.keys(rows[0]) : [];
  const sum = measure ? rows.reduce((s, r) => s + (typeof r[measure] === "number" ? (r[measure] as number) : 0), 0) : null;
  return (
    <section className="rounded-lg border border-accent/40 bg-white" aria-label={`Rows behind ${title}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold">Rows behind “{title}”</h3>
          <p className="text-xs text-zinc-500">
            {rows.length.toLocaleString("en-US")} row{rows.length === 1 ? "" : "s"}
            {sum != null ? ` · ${measure} adds up to ${fmtNum(sum, currency)}` : ""}
            {rows.length > shown.length ? ` · first ${shown.length} shown` : ""}
          </p>
        </div>
        <div className="flex gap-1">
          {onFilter && <button type="button" onClick={onFilter} className="rounded-md px-2 py-1 text-sm text-accent hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Filter the dashboard to this</button>}
          <button type="button" onClick={onClose} className="rounded-md px-2 py-1 text-sm text-zinc-500 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Close</button>
        </div>
      </div>
      <div className="max-h-80 overflow-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead className="sticky top-0 bg-zinc-50 text-xs text-zinc-500">
            <tr>{cols.map((c) => <th key={c} className="whitespace-nowrap px-3 py-1.5 font-medium">{c === "row_number" ? "Excel row" : c}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {shown.map((r, i) => (
              <tr key={i}>{cols.map((c) => <td key={c} className="max-w-[16rem] truncate whitespace-nowrap px-3 py-1.5 tabular-nums">{cell(r[c])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
