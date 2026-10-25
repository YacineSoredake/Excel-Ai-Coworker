"use client";

import { fmtNum } from "@/lib/chartOption";
import type { ContextRow } from "@/lib/types";

/** Report §4.3: what the workbook seems to be, with the evidence and the uncertainty stated. */
export default function AboutCard({ context, onAsk }: { context: ContextRow; onAsk: (text: string) => void }) {
  const c = context;
  const unsure = c.domain.confidence < 0.6;
  return (
    <section aria-labelledby="about" className="rounded-2xl border border-accent/15 bg-gradient-to-br from-white to-[#f2f3ff] p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent">The quick read</p><h2 id="about" className="mt-1 text-lg font-semibold tracking-tight text-zinc-950">About this workbook</h2></div><span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-medium text-accent">AI-assisted profile</span></div>
      <p className="mt-1.5 text-sm">
        {unsure ? "Possibly " : ""}<span className="font-medium">{c.purpose.toLowerCase()}</span>
        {c.domain.evidence.length > 0 && <span className="text-zinc-500"> (based on columns such as {c.domain.evidence.slice(0, 4).join(", ")})</span>}
        {c.time && <>, covering <span className="font-medium">{c.time.from} to {c.time.to}</span></>}
        {" "}· {fmtNum(c.rows)} rows in {c.tables} table{c.tables === 1 ? "" : "s"}.
      </p>
      {c.uncertainty && <p className="mt-1 text-sm text-amber-900">{c.uncertainty}</p>}
      <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-x-4 gap-y-1 text-sm">
        {c.entities.length > 0 && (<><dt className="text-zinc-500">Looks at</dt><dd>{c.entities.map((e) => `${e.label.toLowerCase()} (${e.columns.join(", ")})`).join(" · ")}</dd></>)}
        {c.measures.length > 0 && (<><dt className="text-zinc-500">Measures</dt><dd>{c.measures.map((m) => m.name).join(", ")}</dd></>)}
      </dl>
      {c.potential_analyses.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-zinc-500">Analyses this data supports</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">{c.potential_analyses.map((a) => <li key={a}>{a}</li>)}</ul>
        </div>
      )}
      {c.suggested_questions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Questions to start with">
          {c.suggested_questions.slice(0, 3).map((q) => (
            <button key={q.text} type="button" onClick={() => onAsk(q.text)}
              className="rounded-full border border-zinc-300 px-3 py-1 text-left text-xs hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{q.text}</button>
          ))}
        </div>
      )}
      <details className="mt-3 text-xs text-zinc-600">
        <summary className="cursor-pointer text-zinc-500 hover:text-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">Assumptions made</summary>
        <ul className="mt-1.5 list-disc space-y-0.5 pl-4">{c.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </details>
    </section>
  );
}
