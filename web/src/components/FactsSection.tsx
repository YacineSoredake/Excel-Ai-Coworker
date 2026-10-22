"use client";

import { useState } from "react";
import type { FactKind, FactRow } from "@/lib/types";

const GROUPS: { id: string; title: string; note: string; kinds: FactKind[] }[] = [
  { id: "figures", title: "Key figures", note: "Totals and averages over the whole table.", kinds: ["kpi"] },
  { id: "time", title: "Trends and changes", note: "Only complete periods are compared.", kinds: ["trend", "period_change", "swing", "anomaly_period"] },
  { id: "where", title: "Where it comes from", note: "Rankings and breakdowns by category.", kinds: ["ranking", "breakdown"] },
  { id: "targets", title: "Against targets", note: "Actual values compared with a target column.", kinds: ["target"] },
  { id: "assoc", title: "Associations", note: "Columns that move together. This is not proof that one causes the other.", kinds: ["correlation"] },
  { id: "checks", title: "Consistency and unusual values", note: "Things worth a second look.", kinds: ["derivation", "anomaly_values"] },
];
const SHOW = 5;

const n = (v: number | null | undefined, cur?: string | null) => {
  if (v == null) return "–";
  const s = Math.abs(v) >= 1000 || Number.isInteger(v)
    ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return cur ? `${s} ${cur}` : s;
};
const pc = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);

function reliabilityLabel(r: number) {
  return r >= 0.8 ? "High reliability" : r >= 0.6 ? "Medium reliability" : "Lower reliability";
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-1.5 text-left text-xs font-medium text-zinc-500">{children}</th>;
}
const Td = ({ children, right }: { children: React.ReactNode; right?: boolean }) => (
  <td className={`px-3 py-1.5 ${right ? "text-right tabular-nums" : ""}`}>{children}</td>
);

function DataTable({ f }: { f: FactRow }) {
  const p = f.payload;
  const cur = p.currency as string | null | undefined;
  const wrap = (head: React.ReactNode, body: React.ReactNode) => (
    <div className="mt-3 overflow-x-auto rounded-md border border-zinc-200">
      <table className="w-full text-sm"><thead className="bg-zinc-50"><tr>{head}</tr></thead>
        <tbody className="divide-y divide-zinc-100">{body}</tbody></table>
    </div>
  );
  switch (f.kind) {
    case "trend":
      return wrap(<><Th>Period</Th><Th>Value</Th><Th>Rows</Th><Th>Note</Th></>,
        (p.periods as { period: string; value: number | null; rows: number; complete: boolean; empty: boolean }[]).map((r) => (
          <tr key={r.period}><Td>{r.period}</Td><Td right>{n(r.value, cur)}</Td><Td right>{r.rows}</Td>
            <Td>{!r.complete ? "incomplete, not compared" : r.empty ? "no rows" : ""}</Td></tr>)));
    case "ranking":
      return wrap(<><Th>{f.dimension}</Th><Th>Value</Th><Th>Share</Th><Th>Rows</Th></>, <>
        {(p.groups as { label: string; value: number; share: number | null; rows: number }[]).map((g) => (
          <tr key={g.label}><Td>{g.label}</Td><Td right>{n(g.value, cur)}</Td><Td right>{pc(g.share)}</Td><Td right>{g.rows}</Td></tr>))}
        {p.other && <tr><Td>Other ({p.other.n_groups})</Td><Td right>{n(p.other.value, cur)}</Td><Td right>{pc(p.other.share)}</Td><Td right>–</Td></tr>}
      </>);
    case "target":
      return wrap(<><Th>Month</Th><Th>Actual</Th><Th>Target</Th><Th>Reached</Th></>,
        (p.periods as { period: string; actual: number; target: number; attainment: number | null }[]).map((r) => (
          <tr key={r.period}><Td>{r.period}</Td><Td right>{n(r.actual, cur)}</Td><Td right>{n(r.target, cur)}</Td><Td right>{pc(r.attainment)}</Td></tr>)));
    case "breakdown":
      return wrap(<><Th>{f.dimension}</Th><Th>Total over {p.periods.length} periods</Th></>,
        (p.series as { label: string; total: number }[]).map((s) => (
          <tr key={s.label}><Td>{s.label}</Td><Td right>{n(s.total, cur)}</Td></tr>)));
    case "derivation":
      return p.mismatches?.length ? wrap(<><Th>Excel row</Th><Th>Actual</Th><Th>Expected</Th></>,
        (p.mismatches as { row: number; actual: number; expected: number }[]).map((m) => (
          <tr key={m.row}><Td>{m.row}</Td><Td right>{n(m.actual)}</Td><Td right>{n(m.expected)}</Td></tr>))) : null;
    case "anomaly_values":
      return wrap(<><Th>Excel row</Th><Th>Value</Th></>,
        (p.examples as { row: number; value: number }[]).map((m) => (
          <tr key={m.row}><Td>{m.row}</Td><Td right>{n(m.value, cur)}</Td></tr>)));
    case "anomaly_period":
      return wrap(<><Th>Period</Th><Th>Value</Th></>,
        (p.flagged as { period: string; value: number }[]).map((m) => (
          <tr key={m.period}><Td>{m.period}</Td><Td right>{n(m.value, cur)}</Td></tr>)));
    case "correlation":
      return <p className="mt-3 text-sm text-zinc-600">Rank correlation {Number(p.rho).toFixed(2)} over {p.n} rows.</p>;
    default:
      return null;
  }
}

function FactCard({ f }: { f: FactRow }) {
  const src = f.source ?? {};
  return (
    <li className="rounded-lg border border-zinc-200 bg-white">
      <details>
        <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
          <span className="text-sm font-medium">{f.headline}</span>
          <span className="shrink-0 text-xs text-zinc-500">{reliabilityLabel(f.reliability)}</span>
        </summary>
        <div className="border-t border-zinc-100 px-4 py-3 text-sm">
          <p className="text-zinc-500">{f.title}</p>
          <p className="mt-1.5 text-zinc-700">{f.definition}</p>
          {f.caveats.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-amber-900">
              {f.caveats.map((c) => <li key={c}>{c}</li>)}
            </ul>
          )}
          <DataTable f={f} />
          <p className="mt-3 text-xs text-zinc-500">
            {[src.table, (src.columns as string[] | undefined)?.join(", ")].filter(Boolean).join(" › ")}
            {src.rows_used != null ? ` · ${Number(src.rows_used).toLocaleString("en-US")} rows used` : ""}
            {f.sample_rows.length ? ` · Excel rows behind it: ${f.sample_rows.join(", ")}` : ""}
            {f.verified ? " · recomputed independently and matched" : ""}
          </p>
        </div>
      </details>
    </li>
  );
}

export default function FactsSection({ facts, analyticsError }: { facts: FactRow[]; analyticsError?: string | null }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (analyticsError)
    return <p className="mt-8 text-sm text-zinc-500">Figures and trends could not be computed for this file ({analyticsError}). The profile below is still valid.</p>;
  if (facts.length === 0)
    return <p className="mt-8 text-sm text-zinc-500">This workbook has no numeric columns or dates to compute figures from.</p>;
  return (
    <section aria-labelledby="facts" className="mt-8">
      <h2 id="facts" className="text-sm font-medium text-zinc-700">Key figures and patterns</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Every figure was computed from your data and then recomputed a second way. Open one to see how, what it excludes, and the numbers behind it.
      </p>
      <div className="mt-4 space-y-6">
        {GROUPS.map((g) => {
          const items = facts.filter((f) => g.kinds.includes(f.kind));
          if (!items.length) return null;
          const shown = open[g.id] ? items : items.slice(0, SHOW);
          return (
            <div key={g.id}>
              <h3 className="text-sm font-semibold">{g.title}</h3>
              <p className="text-xs text-zinc-500">{g.note}</p>
              <ul className="mt-2 space-y-2">{shown.map((f) => <FactCard key={f.id} f={f} />)}</ul>
              {items.length > SHOW && (
                <button type="button" onClick={() => setOpen({ ...open, [g.id]: !open[g.id] })}
                  className="mt-2 rounded-md px-2 py-1 text-sm text-accent hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                  {open[g.id] ? "Show fewer" : `Show all ${items.length}`}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
