"use client";

import { useState } from "react";
import { distinctValues, type Filters, type Row } from "@/lib/dataEngine";

export interface FilterDim { name: string }

export default function FilterBar({ filters, onChange, timeCol, bounds, dims, rows, ensureRows, loading, shown, total }: {
  filters: Filters; onChange: (f: Filters) => void; timeCol: string | null; bounds: { min?: string; max?: string };
  dims: FilterDim[]; rows: Row[] | null; ensureRows: () => void; loading: boolean; shown: number | null; total: number | null;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const active = !!(filters.from || filters.to || Object.values(filters.dims).some((v) => v.length));
  if (!timeCol && dims.length === 0) return null;

  const setDim = (col: string, value: string, on: boolean) => {
    const cur = new Set(filters.dims[col] ?? []);
    on ? cur.add(value) : cur.delete(value);
    ensureRows();
    onChange({ ...filters, timeCol, dims: { ...filters.dims, [col]: [...cur] } });
  };

  return (
    <div className="flex flex-wrap items-end gap-x-4 gap-y-3 rounded-2xl border border-zinc-200/80 bg-white px-4 py-3 shadow-sm" role="group" aria-label="Filters">
      {timeCol && (
        <>
          <label className="text-xs text-zinc-500">From
            <input type="date" value={filters.from ?? ""} min={bounds.min} max={bounds.max}
              onChange={(e) => { ensureRows(); onChange({ ...filters, timeCol, from: e.target.value || null }); }}
              className="mt-0.5 block rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
          </label>
          <label className="text-xs text-zinc-500">To
            <input type="date" value={filters.to ?? ""} min={bounds.min} max={bounds.max}
              onChange={(e) => { ensureRows(); onChange({ ...filters, timeCol, to: e.target.value || null }); }}
              className="mt-0.5 block rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
          </label>
        </>
      )}
      {dims.map((d) => {
        const sel = filters.dims[d.name] ?? [];
        const values = rows ? distinctValues(rows, d.name) : [];
        return (
          <div key={d.name} className="relative">
            <button type="button" aria-expanded={open === d.name}
              onClick={() => { ensureRows(); setOpen(open === d.name ? null : d.name); }}
              className="rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              {d.name}{sel.length ? <span className="ml-1.5 rounded bg-accent-soft px-1.5 text-xs text-accent-dark">{sel.length}</span> : null}
            </button>
            {open === d.name && (
              <div className="absolute z-10 mt-1 max-h-64 min-w-[12rem] overflow-auto rounded-md border border-zinc-200 bg-white p-2 shadow-sm">
                {!rows ? <p className="px-1 py-1 text-xs text-zinc-500">{loading ? "Loading the data…" : "Could not load the data."}</p> :
                  values.map((v) => (
                    <label key={v.value} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-zinc-50">
                      <input type="checkbox" checked={sel.includes(v.value)} onChange={(e) => setDim(d.name, v.value, e.target.checked)} />
                      <span className="truncate">{v.value}</span><span className="ml-auto text-xs text-zinc-400">{v.count}</span>
                    </label>
                  ))}
              </div>
            )}
          </div>
        );
      })}
      {active && (
        <div className="ml-auto flex items-center gap-3 text-xs text-zinc-500">
          {loading && !rows ? "Loading the data to apply filters…" : shown != null && total != null ? `Showing ${shown.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} rows` : null}
          <button type="button" onClick={() => { setOpen(null); onChange({ timeCol, dims: {} }); }}
            className="rounded-md px-2 py-1 text-sm text-accent hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Clear filters</button>
        </div>
      )}
    </div>
  );
}
