"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChartCard from "@/components/ChartCard";
import KpiCard from "@/components/KpiCard";
import { fmtNum } from "@/lib/chartOption";
import { supabase } from "@/lib/supabase";
import type { Answer, ChartKind, ChartRow, ContextRow, PlanLike, QuestionRow } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const noop = () => {};
const PLAN_LABEL = { ai: "Question understood by AI, then checked", rules: "Question understood by built-in logic", suggested: "Suggested question" } as const;

function chartRow(q: QuestionRow, a: Answer): ChartRow | null {
  if (!a.chart || a.chart.kind === "table") return null;
  return { id: q.id, table_id: null, key: `answer:${q.id}`, kind: a.chart.kind as ChartKind, role: "answer", placement: "explore", position: 0,
    title: q.text, why: a.chart.why ?? "", fact_keys: [], encoding: {}, data: a.chart.data, query: null, options: a.chart.options ?? {},
    usefulness: 1, reliability: 1, readability: 1, score: 1, caveats: a.caveats };
}

/** The question without any earlier "(use …)" choices, so a clarification is applied once instead of piling up. */
export function baseQuestion(text: string): string {
  return text.replace(/\s*\(use [^)]*\)/g, "").trim();
}

function Chips({ items, onAsk }: { items: { text: string; plan?: PlanLike }[]; onAsk: (t: string, p?: PlanLike) => void }) {
  if (!items.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((s) => (
        <button key={s.text} type="button" onClick={() => onAsk(s.text, s.plan)}
          className="rounded-full border border-zinc-300 px-3 py-1 text-left text-xs hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{s.text}</button>
      ))}
    </div>
  );
}

function RowsTable({ data }: { data: any }) {
  return (
    <div className="mt-3 max-h-72 overflow-auto rounded-md border border-zinc-200">
      <table className="w-full min-w-[28rem] text-left text-sm">
        <thead className="sticky top-0 bg-zinc-50 text-xs text-zinc-500"><tr>{data.columns.map((c: string) => <th key={c} className="whitespace-nowrap px-3 py-1.5 font-medium">{c}</th>)}</tr></thead>
        <tbody className="divide-y divide-zinc-100">
          {data.rows.map((r: unknown[], i: number) => (
            <tr key={i}>{r.map((v, j) => <td key={j} className="whitespace-nowrap px-3 py-1.5 tabular-nums">{typeof v === "number" ? fmtNum(v) : (v ?? "–") as string}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AnswerView({ q, onAsk }: { q: QuestionRow; onAsk: (t: string, p?: PlanLike) => void }) {
  const a = q.answer;
  if (q.status === "queued" || q.status === "answering")
    return <p role="status" className="mt-2 text-sm text-zinc-500">Working on it…</p>;
  if (!a) return <p className="mt-2 text-sm text-red-600">No answer was produced. Please try again.</p>;
  const row = chartRow(q, a);
  return (
    <div className="mt-2">
      <p className={`text-sm ${a.status === "ok" ? "" : a.status === "error" ? "text-red-700" : "text-zinc-700"}`}>{a.text}</p>
      {a.status === "ok" && row && (
        row.kind === "kpi" ? <div className="mt-3 max-w-xs"><KpiCard chart={row} data={row.data} filtered={false} /></div>
          : <div className="mt-3"><ChartCard chart={row} data={row.data} filtered={false} onSelect={noop} height={220} /></div>
      )}
      {a.status === "ok" && a.chart?.kind === "table" && <RowsTable data={a.chart.data} />}
      {a.status === "ok" && a.result?.kind === "highlights" && (
        <ol className="mt-3 space-y-3">
          {(a.result.data.items as { statement: string; next_check: string; next_plan: PlanLike | null }[]).map((it, i) => (
            <li key={i} className="text-sm">
              <p className="font-medium">{it.statement}</p>
              {it.next_check && it.next_plan && (
                <button type="button" onClick={() => onAsk(it.next_check, it.next_plan ?? undefined)}
                  className="mt-0.5 rounded text-xs text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{it.next_check}</button>
              )}
            </li>
          ))}
        </ol>
      )}
      {a.status === "clarify" && a.options && (
        <Chips items={a.options.map((o) => ({ text: `${baseQuestion(q.text)} (use ${o})` }))} onAsk={onAsk} />
      )}
      {a.status === "unsupported" && (
        <>
          {a.options && a.options.length > 0 && !a.suggestions && <p className="mt-1 text-xs text-zinc-500">Did you mean: {a.options.join(", ")}?</p>}
          <Chips items={a.suggestions ?? []} onAsk={onAsk} />
        </>
      )}
      {a.status === "ok" && a.plan_summary && (
        <details className="mt-3 text-xs text-zinc-600">
          <summary className="cursor-pointer text-zinc-500 hover:text-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">How was this computed?</summary>
          <div className="mt-1.5 space-y-1">
            <p><span className="font-medium">Calculation:</span> {a.plan_summary}</p>
            {a.result && <p>Based on {a.result.rows_used.toLocaleString("en-US")} of {a.result.rows_after_filters.toLocaleString("en-US")} rows after filters. Computed from your data and then checked a second way.</p>}
            {a.sample_rows.length > 0 && <p>Excel rows behind it include: {a.sample_rows.slice(0, 8).join(", ")}.</p>}
            {a.notes.map((n) => <p key={n}>{n}</p>)}
            {a.caveats.length > 0 && <ul className="list-disc pl-4 text-amber-900">{a.caveats.map((c) => <li key={c}>{c}</li>)}</ul>}
            <p className="text-zinc-500">
              {a.source.plan ? PLAN_LABEL[a.source.plan] : ""} · {a.source.text === "ai" ? "Wording by AI; every number matches the result" : "Built-in wording"}
            </p>
          </div>
        </details>
      )}
      {a.status === "ok" && a.result?.kind !== "highlights" && <Chips items={a.followups} onAsk={onAsk} />}
    </div>
  );
}

export default function AskPanel({ workbookId, context, initial }: {
  workbookId: string; context: ContextRow | null; initial: { text: string; plan: PlanLike | null; nonce: number } | null;
}) {
  const [items, setItems] = useState<QuestionRow[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handled = useRef<number | null>(null);

  const load = useCallback(async () => {
    const { data } = await supabase.from("questions").select("id, workbook_id, text, status, answer, created_at")
      .eq("workbook_id", workbookId).order("created_at", { ascending: false }).limit(30);
    if (data) setItems(data as QuestionRow[]);
  }, [workbookId]);

  useEffect(() => { void load(); }, [load]);
  const pending = items.some((i) => i.status === "queued" || i.status === "answering");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => void load(), 1500);
    return () => clearInterval(t);
  }, [pending, load]);

  const ask = useCallback(async (q: string, plan?: PlanLike | null) => {
    const t = q.trim();
    if (!t || t.length > 500) { setError("Please ask a question of up to 500 characters."); return; }
    setBusy(true); setError(null);
    const { error } = await supabase.from("questions").insert({ workbook_id: workbookId, text: t, plan: plan ?? null });
    if (error) setError(/rate_limited/.test(error.message) ? "You have asked a lot of questions in the last hour. Please try again a little later." : "Could not send the question. Please try again.");
    else { setText(""); await load(); }
    setBusy(false);
  }, [workbookId, load]);

  useEffect(() => {
    if (initial && handled.current !== initial.nonce) { handled.current = initial.nonce; void ask(initial.text, initial.plan); }
  }, [initial, ask]);

  const chips = (context?.suggested_questions ?? []).slice(0, 4);
  return (
    <div className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); void ask(text); }} className="flex gap-2" role="search" aria-label="Ask a question about this workbook">
        <label className="sr-only" htmlFor="ask">Your question</label>
        <input id="ask" value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
          placeholder="Ask about your data, for example: which category has the highest sales?"
          className="min-w-0 flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" />
        <button type="submit" disabled={busy || !text.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">Ask</button>
      </form>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {items.length === 0 && <Chips items={chips} onAsk={(t, p) => void ask(t, p)} />}
      <ul className="space-y-3">
        {items.map((q) => (
          <li key={q.id} className="rounded-lg border border-zinc-200 bg-white p-4">
            <h3 className="text-sm font-semibold">{q.text}</h3>
            <AnswerView q={q} onAsk={(t, p) => void ask(t, p)} />
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="text-sm text-zinc-500">Answers are computed from your data, never guessed.</p>}
    </div>
  );
}
