"use client";

import type { InsightRow, PlanLike } from "@/lib/types";

const LABEL: Record<string, string> = {
  target: "Against target", period_change: "Latest change", concentration: "Concentration", trend: "Trend", contributors: "Top contributors",
  anomaly: "Unusual", consistency: "Consistency", association: "Association", quality: "Data quality",
};

/** Observation, hedged possibility, and what to check next, kept visibly separate (report §6.3). */
export default function InsightsPanel({ insights, onAsk, onDetails }: {
  insights: InsightRow[]; onAsk: (text: string, plan: PlanLike | null) => void; onDetails: () => void;
}) {
  if (!insights.length) return null;
  return (
    <section aria-labelledby="insights" className="rounded-2xl border border-zinc-200/80 bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent">Decision signals</p><h2 id="insights" className="mt-1 text-lg font-semibold tracking-tight text-zinc-950">What stands out</h2></div>
        <p className="max-w-xs text-right text-xs leading-5 text-zinc-500">Every number below was computed and checked against your data.</p>
      </div>
      <ol className="mt-3 divide-y divide-zinc-100">
        {insights.map((i, n) => (
          <li key={i.id} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 w-28 shrink-0 text-xs text-zinc-500">{LABEL[i.category] ?? i.category}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{i.statement}</p>
                {i.interpretation && (
                  <p className="mt-1 text-sm text-zinc-600"><span className="text-xs text-zinc-500">A possibility, not shown by the data: </span>{i.interpretation}</p>
                )}
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  {i.next_check && !insights.slice(0, n).some((p) => p.next_check === i.next_check) && (i.next_plan
                    ? <button type="button" onClick={() => onAsk(i.next_check, i.next_plan)} className="rounded text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{i.next_check}</button>
                    : <button type="button" onClick={onDetails} className="rounded text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{i.next_check}</button>)}
                  <span className="text-zinc-400">{i.source === "ai" ? "Worded by AI, numbers checked" : "Built-in summary"}</span>
                </div>
                {i.caveats.length > 0 && (
                  <details className="mt-1 text-xs text-zinc-600">
                    <summary className="cursor-pointer text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Caveats</summary>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-amber-900">{i.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
                  </details>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
