"use client";

import { fmtNum } from "@/lib/chartOption";
import type { ChartRow } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function KpiCard({ chart, data, filtered }: { chart: ChartRow; data: Record<string, any>; filtered: boolean }) {
  const isPct = data.format === "percent";
  const value = isPct ? (data.value == null ? "–" : `${Math.round(data.value * 100)}%`) : fmtNum(data.value, data.currency);
  const d = data.delta as { pct: number | null; previous: string } | null | undefined;
  const sub = data.sub ?? (data.median != null && chart.data.label?.startsWith("Average") ? `median ${fmtNum(data.median, data.currency)}` : null);
  return (
    <div className="group relative rounded-2xl border border-zinc-200/80 bg-white p-5 shadow-sm transition-shadow hover:shadow-md" title={chart.title}>
      <p className="text-xs font-medium uppercase tracking-[0.12em] text-zinc-500">{data.label}</p><span className="absolute right-5 top-5 h-2 w-2 rounded-full bg-accent/70" aria-hidden />
      <p className="mt-3 text-3xl font-semibold tracking-tight tabular-nums text-zinc-950">{value}</p>
      {isPct && data.value != null && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-100" aria-hidden>
          <div className="h-full rounded bg-accent" style={{ width: `${Math.min(100, Math.round(data.value * 100))}%` }} />
        </div>
      )}
      <p className="mt-2 min-h-[1rem] text-xs text-zinc-500">
        {d && d.pct != null ? (
          <>
            <span aria-hidden>{d.pct >= 0 ? "▲" : "▼"} </span>
            <span className="font-medium text-zinc-700">{`${d.pct >= 0 ? "+" : ""}${Math.round(d.pct * 100)}%`}</span>
            <span className="sr-only">{d.pct >= 0 ? " increase" : " decrease"}</span> vs {d.previous}
          </>
        ) : sub ?? (chart.query === null && filtered ? "not affected by filters" : "")}
      </p>
    </div>
  );
}
