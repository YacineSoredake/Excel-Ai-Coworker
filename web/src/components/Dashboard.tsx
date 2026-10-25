"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChartCard from "@/components/ChartCard";
import DrillPanel from "@/components/DrillPanel";
import FilterBar from "@/components/FilterBar";
import AboutCard from "@/components/AboutCard";
import InsightsPanel from "@/components/InsightsPanel";
import KpiCard from "@/components/KpiCard";
import {
  NO_FILTERS, applyFilters, coverage, filtersActive, matchRows, periodRange, runChart,
  type ChartQuery, type Filters, type Grain, type Selection,
} from "@/lib/dataEngine";
import { prefersReducedMotion } from "@/lib/motion";
import { useTableRows } from "@/lib/useTableRows";
import type { ChartRow, ContextRow, DataTableRow, InsightRow, PlanLike } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
export interface ColLite { id: string; table_id: string; position: number; name: string; data_type: string; role: string; role_subtype: string | null; distinct_count: number; stats: Record<string, any> }
export interface FactLite { id: string; table_id: string | null; kind: string; headline: string; score: number; payload: Record<string, any> }

const EXPLORE_GROUPS: { title: string; match: (c: ChartRow, subtype: string | null) => boolean }[] = [
  { title: "Trends over time", match: (c) => c.role === "trend" },
  { title: "Products", match: (c, s) => c.role === "comparison" && s === "product" },
  { title: "Regions", match: (c, s) => c.role === "comparison" && s === "location" },
  { title: "People", match: (c, s) => c.role === "comparison" && s === "person" },
  { title: "Other comparisons", match: (c, s) => c.role === "comparison" && !["product", "location", "person"].includes(s ?? "") },
  { title: "Breakdowns over time", match: (c) => c.role === "breakdown" },
  { title: "Relationships between numbers", match: (c) => c.role === "relationship" },
  { title: "Distributions", match: (c) => c.role === "distribution" },
  { title: "Against targets", match: (c) => c.role === "target" },
];

export default function Dashboard({ view, tables, columns, charts, facts, findings, onOpenDetails, context = null, insights = [], onAsk = () => {}, onGuide }: {
  view: "overview" | "explore"; tables: DataTableRow[]; columns: ColLite[]; charts: ChartRow[]; facts: FactLite[];
  findings: Record<string, number>; onOpenDetails: () => void;
  context?: ContextRow | null; insights?: InsightRow[]; onAsk?: (text: string, plan: PlanLike | null) => void; onGuide?: () => void;
}) {
  const withCharts = useMemo(() => tables.filter((t) => charts.some((c) => c.table_id === t.id)), [tables, charts]);
  const [tableId, setTableId] = useState<string | null>(null);
  const [filtersBy, setFiltersBy] = useState<Record<string, Filters>>({});
  const [drill, setDrill] = useState<{ chart: ChartRow; sel: Selection; title: string } | null>(null);
  const drillRef = useRef<HTMLDivElement>(null);
  const { ensure, rowsOf, state } = useTableRows();

  const table = withCharts.find((t) => t.id === tableId) ??
    withCharts.find((t) => charts.some((c) => c.table_id === t.id && c.placement === "primary")) ?? withCharts[0];
  const tcharts = useMemo(() => charts.filter((c) => c.table_id === table?.id), [charts, table]);
  const tcols = useMemo(() => columns.filter((c) => c.table_id === table?.id), [columns, table]);
  const timeCol: string | null = tcharts.find((c) => c.encoding?.time)?.encoding.time ?? tcols.find((c) => c.role === "time")?.name ?? null;
  const tc = tcols.find((c) => c.name === timeCol);
  const bounds = { min: tc?.stats?.min?.slice(0, 10), max: tc?.stats?.max?.slice(0, 10) };
  const filterDims = tcols.filter((c) => c.role === "dimension" && c.data_type === "text" && c.distinct_count >= 2 && c.distinct_count <= 30)
    .sort((a, b) => a.position - b.position).slice(0, 4).map((c) => ({ name: c.name }));

  const filters = (table && filtersBy[table.id]) || NO_FILTERS;
  const active = filtersActive(filters);
  const rows = table ? rowsOf(table.id) : null;
  const loading = !!table && state[table.id] === "loading";
  const failed = !!table && state[table.id] === "error";
  const ensureRows = useCallback(() => { if (table) void ensure(table); }, [table, ensure]);
  const setFilters = (f: Filters) => table && setFiltersBy((m) => ({ ...m, [table.id]: f }));

  const filtered = useMemo(() => (rows && active ? applyFilters(rows, filters) : rows), [rows, filters, active]);
  const ctx = useMemo(() => (rows ? coverage(rows, filters, timeCol) : null), [rows, filters, timeCol]);
  const dataOf = useMemo(() => {
    const m = new Map<string, any>();
    for (const c of tcharts) {
      let d = c.data;
      if (active && filtered && ctx && c.query) {
        try { d = runChart(c.kind, c.data, c.query as ChartQuery, filtered, ctx); } catch { d = c.data; }
      }
      m.set(c.key, d);
    }
    return m;
  }, [tcharts, active, filtered, ctx]);

  const onSelect = useCallback(async (chart: ChartRow, sel: Selection, title: string) => {
    if (table) await ensure(table);
    setDrill({ chart, sel, title });
  }, [table, ensure]);

  useEffect(() => {
    if (drill) drillRef.current?.scrollIntoView?.({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "nearest" });
  }, [drill]);

  const drillRows = useMemo(() => (drill && filtered && drill.chart.query ? matchRows(filtered, drill.chart.query as ChartQuery, drill.sel) : []), [drill, filtered]);
  const filterToDrill = () => {
    if (!drill) return;
    const q = drill.chart.query as any, s = drill.sel;
    const f: Filters = { ...filters, timeCol, dims: { ...filters.dims } };
    if (s.type === "group" || s.type === "breakdown") f.dims[q.dim] = [s.label];
    if (s.type === "period" || s.type === "breakdown") {
      const r = periodRange(s.period, (q.grain ?? q.delta?.grain) as Grain);
      if (r) { f.from = r.from; f.to = r.to; }
    }
    setFilters(f);
    setDrill(null);
  };

  if (!table) return <p className="text-sm text-zinc-500">No charts could be built for this workbook. See Details for what was found.</p>;

  const kpis = tcharts.filter((c) => c.placement === "kpi").sort((a, b) => a.position - b.position);
  const primary = tcharts.find((c) => c.placement === "primary");
  const secondary = tcharts.filter((c) => c.placement === "secondary").sort((a, b) => a.position - b.position);
  const explore = tcharts.filter((c) => c.placement === "explore").sort((a, b) => a.position - b.position);
  const subtypeOf = (c: ChartRow) => tcols.find((x) => x.name === c.encoding?.dim)?.role_subtype ?? null;
  const card = (c: ChartRow, h?: number) => <ChartCard key={c.key} chart={c} data={dataOf.get(c.key)} filtered={active} onSelect={onSelect} height={h} />;

  const worth = facts.filter((f) => f.table_id === table.id && (["anomaly_values", "anomaly_period", "swing"].includes(f.kind) ||
    (f.kind === "derivation" && f.payload.mismatch_count > 0))).slice(0, 3);
  const issues = (findings.high ?? 0) + (findings.medium ?? 0) + (findings.low ?? 0);

  return (
    <div className="space-y-6">
      {withCharts.length > 1 && (
        <label className="block text-xs text-zinc-500">Table
          <select value={table.id} onChange={(e) => { setTableId(e.target.value); setDrill(null); }}
            className="ml-2 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {withCharts.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.row_count.toLocaleString("en-US")} rows)</option>)}
          </select>
        </label>
      )}
      <FilterBar filters={filters} onChange={setFilters} timeCol={timeCol} bounds={bounds} dims={filterDims} rows={rows}
        ensureRows={ensureRows} loading={loading} shown={filtered?.length ?? null} total={rows?.length ?? null} />
      {failed && <p role="alert" className="text-sm text-amber-900">The cleaned data for this table could not be loaded, so filters and row details are unavailable. Re-uploading the file regenerates it.</p>}

      {view === "overview" ? (
        <>
          {onGuide && (
            <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 px-5 py-5 text-white shadow-lg shadow-zinc-950/10">
              <div className="absolute -right-12 -top-16 h-40 w-40 rounded-full bg-accent/30 blur-2xl" aria-hidden />
              <div className="relative flex flex-wrap items-center justify-between gap-4">
                <div><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-200">Your guided briefing</p><p className="mt-1 text-base font-medium">Start with the signals that deserve your attention.</p><p className="mt-1 text-sm text-zinc-400">A short, evidence-based tour through this workbook.</p></div>
                <button type="button" onClick={onGuide} className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">Walk me through it <span aria-hidden>→</span></button>
              </div>
            </div>
          )}
          {context && <AboutCard context={context} onAsk={(t) => onAsk(t, context.suggested_questions.find((q) => q.text === t)?.plan ?? null)} />}
          {kpis.length > 0 && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {kpis.map((c) => <KpiCard key={c.key} chart={c} data={dataOf.get(c.key)} filtered={active} />)}
            </div>
          )}
          {primary && <section aria-label="Primary trend" className="space-y-2"><div className="flex items-end justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Performance over time</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-zinc-950">The main story</h2></div><span className="hidden text-xs text-zinc-400 sm:inline">Click a point to inspect the rows behind it</span></div>{card(primary, 340)}</section>}
          {insights.length > 0 && <InsightsPanel insights={insights.filter((i) => !i.table_id || i.table_id === table.id)} onAsk={onAsk} onDetails={onOpenDetails} />}
          {insights.length === 0 && worth.length > 0 && (
            <section aria-labelledby="worth" className="rounded-lg border border-zinc-200 bg-white p-4">
              <h2 id="worth" className="text-sm font-semibold">Worth a look</h2>
              <ul className="mt-2 space-y-1.5 text-sm">{worth.map((f) => <li key={f.id}>{f.headline}</li>)}</ul>
              <button type="button" onClick={onOpenDetails} className="mt-2 text-sm text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">See how these were computed</button>
            </section>
          )}
          {secondary.length > 0 && <section className="space-y-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Where it comes from</p><h2 className="mt-1 text-lg font-semibold tracking-tight text-zinc-950">Breakdowns worth exploring</h2></div><div className="grid gap-4 md:grid-cols-2">{secondary.map((c) => card(c))}</div></section>}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-200/80 bg-white px-5 py-4 text-sm shadow-sm">
            <div><p className="font-medium text-zinc-900">Data quality</p><span className="text-xs text-zinc-500">{issues === 0 ? "No potential issues found in the analyzed workbook." : `${issues} potential data-quality issue${issues === 1 ? "" : "s"}${findings.high ? ` · ${findings.high} high priority` : ""}.`}</span></div>
            <button type="button" onClick={onOpenDetails} className="text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Review in Details</button>
          </div>
        </>
      ) : (
        <div className="space-y-8">
          {EXPLORE_GROUPS.map((g) => {
            const items = [...(primary && g.match(primary, subtypeOf(primary)) ? [primary] : []), ...secondary.filter((c) => g.match(c, subtypeOf(c))), ...explore.filter((c) => g.match(c, subtypeOf(c)))];
            if (!items.length) return null;
            return (
              <section key={g.title} aria-label={g.title}>
                <h2 className="mb-3 text-sm font-medium text-zinc-700">{g.title}</h2>
                <div className="grid gap-4 md:grid-cols-2">{items.map((c) => card(c, 240))}</div>
              </section>
            );
          })}
          {explore.length === 0 && <p className="text-sm text-zinc-500">Everything worth showing is already on the Overview.</p>}
        </div>
      )}

      <div ref={drillRef}>
        {drill && (
          <DrillPanel title={drill.title} rows={drillRows} measure={drill.chart.kind === "scatter" ? null : drill.chart.encoding?.measure ?? null}
            currency={drill.chart.options?.currency ?? null} onClose={() => setDrill(null)}
            onFilter={drill.sel.type === "group" || drill.sel.type === "period" || drill.sel.type === "breakdown" ? filterToDrill : undefined} />
        )}
      </div>
    </div>
  );
}
