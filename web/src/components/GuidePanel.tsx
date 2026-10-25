"use client";

import { useEffect, useRef, useState } from "react";
import { AnswerView } from "@/components/AskPanel";
import ChartCard from "@/components/ChartCard";
import KpiCard from "@/components/KpiCard";
import { supabase } from "@/lib/supabase";
import type { ChartRow, GuideAction, GuideRow, PlanLike, QuestionRow } from "@/lib/types";

const noop = () => {};

/** Guide Me (report §7): an ordered path through what matters. Any step can be skipped; every button runs inside the step. */
export default function GuidePanel({ guide, charts, workbookId, onDetails, onAskTab, onDone, pollMs = 1500 }: {
  guide: GuideRow; charts: ChartRow[]; workbookId: string; onDetails: () => void; onAskTab: () => void; onDone: () => void; pollMs?: number;
}) {
  const steps = guide.steps;
  const [i, setI] = useState(0);
  const [visited, setVisited] = useState<Set<number>>(new Set([0]));
  const [results, setResults] = useState<Record<string, QuestionRow>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  useEffect(() => () => { Object.values(timers.current).forEach(clearInterval); }, []);

  const byKey = new Map(charts.map((c) => [c.key, c]));
  const step = steps[i];
  const go = (n: number) => { setError(null); setI(n); setVisited((v) => new Set(v).add(n)); };

  async function run(stepId: string, text: string, plan: PlanLike | null) {
    setError(null); setBusy(true);
    const ins = await supabase.from("questions").insert({ workbook_id: workbookId, text, plan }).select("id").single();
    if (ins.error || !ins.data) {
      setError(/rate_limited/.test(ins.error?.message ?? "") ? "You have asked a lot of questions in the last hour. Please try again a little later." : "Could not run that. Please try again.");
      setBusy(false);
      return;
    }
    const id = (ins.data as { id: string }).id;
    setResults((r) => ({ ...r, [stepId]: { id, workbook_id: workbookId, text, status: "queued", answer: null, created_at: new Date().toISOString() } }));
    clearInterval(timers.current[stepId]);
    let tries = 0;
    timers.current[stepId] = setInterval(async () => {
      tries += 1;
      const { data } = await supabase.from("questions").select("id, workbook_id, text, status, answer, created_at").eq("id", id).single();
      const done = !!data && (data.status === "answered" || data.status === "failed");
      if (data) setResults((r) => ({ ...r, [stepId]: data as QuestionRow }));
      if (done || tries > 60) {
        clearInterval(timers.current[stepId]);
        setBusy(false);
        if (!done) setError("This is taking longer than usual. The answer will appear in the Ask tab when it is ready.");
      }
    }, pollMs);
  }

  function act(a: GuideAction) {
    if (a.kind === "details") onDetails();
    else if (a.kind === "ask_tab") onAskTab();
    else if (a.text) void run(step.id, a.text, a.plan);
  }

  const evidence = step.chart_keys.map((k) => byKey.get(k)).filter((c): c is ChartRow => !!c);
  const kpis = evidence.filter((c) => c.kind === "kpi");
  const others = evidence.filter((c) => c.kind !== "kpi");
  const last = i === steps.length - 1;
  const result = results[step.id];

  return (
    <div className="md:grid md:grid-cols-[14rem_1fr] md:gap-8">
      <nav aria-label="Guided steps" className="mb-6 md:mb-0">
        <ol className="space-y-1">
          {steps.map((s, n) => (
            <li key={s.id}>
              <button type="button" onClick={() => go(n)} aria-current={n === i ? "step" : undefined}
                className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${n === i ? "bg-accent-soft font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-100"}`}>
                <span className="mt-px w-4 shrink-0 text-xs text-zinc-400" aria-hidden>{visited.has(n) && n !== i ? "✓" : n + 1}</span>
                <span>{s.title}</span>
              </button>
            </li>
          ))}
        </ol>
        <p className="mt-3 px-2 text-xs text-zinc-500">You can jump to any step, or skip the ones you don&apos;t need.</p>
      </nav>

      <section aria-labelledby="step-title" className="min-w-0">
        <p className="text-xs text-zinc-500">Step {i + 1} of {steps.length}</p>
        <h2 id="step-title" className="mt-1 text-lg font-semibold tracking-tight">{step.title}</h2>
        <p className="mt-2 text-sm">{step.narrative}</p>
        {step.notes && step.notes.length > 0 && (
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-amber-900">{step.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        )}

        {kpis.length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">{kpis.map((c) => <KpiCard key={c.key} chart={c} data={c.data} filtered={false} />)}</div>
        )}
        {others.map((c) => <div key={c.key} className="mt-4"><ChartCard chart={c} data={c.data} filtered={false} onSelect={noop} height={240} /></div>)}

        {step.actions.length > 0 && (
          <div className="mt-5">
            <p className="text-xs text-zinc-500">{last ? "Good places to continue" : "Want to look closer?"}</p>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {step.actions.map((a) => (
                <button key={a.label} type="button" disabled={busy && a.kind === "ask"} onClick={() => act(a)}
                  className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{a.label}</button>
              ))}
            </div>
          </div>
        )}
        {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
        <div aria-live="polite">
          {result && (
            <div className="mt-4 rounded-lg border border-zinc-200 bg-white p-4">
              <h3 className="text-sm font-semibold">{result.text}</h3>
              <AnswerView q={result} onAsk={(t, p) => void run(step.id, t, p ?? null)} />
            </div>
          )}
        </div>

        <div className="mt-6 flex items-center gap-2 border-t border-zinc-200 pt-4">
          <button type="button" onClick={() => go(i - 1)} disabled={i === 0}
            className="rounded-md px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Back</button>
          <button type="button" onClick={() => (last ? onDone() : go(i + 1))}
            className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">
            {last ? "Finish" : i === 0 ? "Start" : "Next"}
          </button>
        </div>
      </section>
    </div>
  );
}
