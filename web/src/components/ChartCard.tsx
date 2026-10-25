"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import { chartOption } from "@/lib/chartOption";
import type { Selection } from "@/lib/dataEngine";
import type { ChartRow } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const EChart = dynamic(() => import("./EChart"), {
  ssr: false,
  loading: () => <div className="h-[240px] rounded bg-zinc-100 motion-safe:animate-pulse" aria-hidden />,
});

function reliabilityLabel(r: number) {
  return r >= 0.8 ? "High" : r >= 0.6 ? "Medium" : "Lower";
}

/** What a click on the chart means, as a selection the data engine understands. */
function selectionFor(chart: ChartRow, data: any, view: string, p: any): Selection | null {
  const i = p.dataIndex as number;
  switch (view) {
    case "hbar": case "donut": {
      const g = data.groups?.[i];
      return g && !g.muted ? { type: "group", label: g.label } : null;
    }
    case "line": return data.x[i] != null ? { type: "period", period: data.x[i] } : null;
    case "stacked_bar": case "multi_line":
      return p.seriesName && p.seriesName !== "Other" ? { type: "breakdown", label: p.seriesName, period: data.x[i] } : null;
    case "scatter": return p.data?.[2] != null ? { type: "row", row: p.data[2] } : null;
    case "histogram": return data.edges?.length ? { type: "bin", lo: data.edges[i], hi: data.edges[i + 1], last: i === data.counts.length - 1 } : null;
    default: return null;
  }
}

export default function ChartCard({ chart, data, filtered, onSelect, height = 260 }: {
  chart: ChartRow; data: any; filtered: boolean; onSelect: (c: ChartRow, s: Selection, title: string) => void; height?: number;
}) {
  const alts: string[] = chart.options.alt_kinds ?? [];
  const [view, setView] = useState<string>(chart.kind);
  const option = useMemo(() => chartOption(chart.kind, data, chart.options, view), [chart, data, view]);
  const drillable = chart.query !== null && chart.kind !== "target";
  const click = useCallback((p: any) => {
    const s = selectionFor(chart, data, view, p);
    if (s) onSelect(chart, s, s.type === "group" ? s.label : s.type === "breakdown" ? `${s.label} · ${s.period}` : s.type === "period" ? s.period : s.type === "row" ? `Excel row ${s.row}` : "Selected values");
  }, [chart, data, view, onSelect]);
  const empty = (data.groups && data.groups.length === 0) || (data.x && data.x.length === 0) || (data.counts && data.counts.length === 0);

  return (
    <section className="rounded-2xl border border-zinc-200/80 bg-white p-5 shadow-sm" aria-label={chart.title}>
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{chart.role === "trend" ? "Trend" : chart.role === "comparison" ? "Comparison" : "Analysis"}</p><h3 className="mt-1 text-sm font-semibold leading-snug text-zinc-950">{chart.title}</h3></div>
        {alts.length > 0 && (
          <div role="group" aria-label="Chart type" className="flex shrink-0 overflow-hidden rounded-md border border-zinc-200 text-xs">
            {[chart.kind, ...alts].map((k) => (
              <button key={k} type="button" aria-pressed={view === k} onClick={() => setView(k)}
                className={`px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${view === k ? "bg-accent-soft font-medium text-accent-dark" : "text-zinc-500 hover:bg-zinc-50"}`}>
                {k === "hbar" ? "Bars" : "Donut"}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="mt-2">
        {empty ? (
          <p className="flex items-center justify-center text-sm text-zinc-500" style={{ height }}>No rows match the current filters.</p>
        ) : (
          <EChart option={option} height={height} label={chart.title} onClick={drillable ? click : undefined} />
        )}
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {filtered && chart.query === null ? "Not affected by filters. " : ""}
        {chart.kind === "scatter" && data.sampled ? `Showing ${data.points.length} of ${data.n.toLocaleString("en-US")} rows. ` : ""}
        {drillable ? "Click a bar or point to see its rows." : ""}
      </p>
      <details className="mt-2 text-xs text-zinc-600">
        <summary className="cursor-pointer text-zinc-500 hover:text-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Why this chart</summary>
        <p className="mt-1.5">{chart.why}</p>
        {chart.caveats.length > 0 && (
          <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-amber-900">{chart.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
        )}
        <p className="mt-1.5 text-zinc-500">
          {chart.role === "answer" ? "Computed from your data and checked a second way"
            : `Built from ${chart.fact_keys.length} verified figure${chart.fact_keys.length === 1 ? "" : "s"} · reliability ${reliabilityLabel(chart.reliability).toLowerCase()}`}
        </p>
      </details>
    </section>
  );
}
