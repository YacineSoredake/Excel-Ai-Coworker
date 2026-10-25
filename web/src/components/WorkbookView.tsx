"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AiConsent from "@/components/AiConsent";
import AskPanel from "@/components/AskPanel";
import Dashboard, { type ColLite } from "@/components/Dashboard";
import GuidePanel from "@/components/GuidePanel";
import ExportReport from "@/components/ExportReport";
import ProfileView from "@/components/ProfileView";
import { supabase } from "@/lib/supabase";
import type { ChartRow, ContextRow, DataTableRow, FactRow, GuideRow, InsightRow, PlanLike } from "@/lib/types";

type Tab = "overview" | "guide" | "ask" | "explore" | "details";
const TABS: { id: Tab; label: string }[] = [{ id: "overview", label: "Overview" }, { id: "guide", label: "Guide" }, { id: "ask", label: "Ask" }, { id: "explore", label: "Explore" }, { id: "details", label: "Details" }];

export default function WorkbookView({ workbookId }: { workbookId: string }) {
  const [state, setState] = useState<"loading" | "error" | "notready" | "ready">("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState("");
  const [tables, setTables] = useState<DataTableRow[]>([]);
  const [columns, setColumns] = useState<ColLite[]>([]);
  const [charts, setCharts] = useState<ChartRow[]>([]);
  const [facts, setFacts] = useState<FactRow[]>([]);
  const [findings, setFindings] = useState<Record<string, number>>({});
  const [context, setContext] = useState<ContextRow | null>(null);
  const [guide, setGuide] = useState<GuideRow | null>(null);
  const [insights, setInsights] = useState<InsightRow[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [aiOn, setAiOn] = useState(false);
  const [serverAi, setServerAi] = useState<boolean | null>(null);
  const [ask, setAsk] = useState<{ text: string; plan: PlanLike | null; nonce: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const wb = await supabase.from("workbooks").select("filename, status").eq("id", workbookId).single();
      if (cancelled) return;
      if (wb.error || !wb.data) { setState("error"); return; }
      setFilename(wb.data.filename);
      setStatus(wb.data.status);
      if (wb.data.status !== "profiled") { setState("notready"); return; }
      const [t, c, ch, f, p, ins, usr] = await Promise.all([
        supabase.from("data_tables").select("*").eq("workbook_id", workbookId).order("position"),
        supabase.from("column_profiles").select("id, table_id, position, name, data_type, role, role_subtype, distinct_count, stats").eq("workbook_id", workbookId),
        supabase.from("charts").select("*").eq("workbook_id", workbookId),
        supabase.from("facts").select("*").eq("workbook_id", workbookId).order("score", { ascending: false }).limit(80),
        supabase.from("workbook_profiles").select("summary, context, analytics, guide").eq("workbook_id", workbookId).single(),
        supabase.from("insights").select("*").eq("workbook_id", workbookId).order("priority"),
        supabase.auth.getUser(),
      ]);
      if (cancelled) return;
      if (t.error || c.error || ch.error || f.error) { setState("error"); return; }
      setTables(t.data as DataTableRow[]);
      setColumns(c.data as ColLite[]);
      setCharts(ch.data as ChartRow[]);
      setFacts(f.data as FactRow[]);
      setFindings((p.data?.summary?.findings_by_severity ?? {}) as Record<string, number>);
      setContext(p.data?.context?.domain ? (p.data.context as ContextRow) : null);
      setInsights((ins.data ?? []) as InsightRow[]);
      setGuide(Array.isArray(p.data?.guide?.steps) && p.data.guide.steps.length ? (p.data.guide as GuideRow) : null);
      const uid = usr.data.user?.id ?? null;
      setUserId(uid);
      if (uid) {
        const us = await supabase.from("user_settings").select("ai_enabled").eq("user_id", uid).maybeSingle();
        if (!cancelled) setAiOn(!!us.data?.ai_enabled);
      }
      const an = p.data?.analytics as { ai_configured?: boolean } | undefined;
      setServerAi(typeof an?.ai_configured === "boolean" ? an.ai_configured : null);
      setState("ready");
    })();
    return () => { cancelled = true; };
  }, [workbookId]);

  const back = (
    <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">← Your files</Link>
  );
  const goAsk = (text: string, plan: PlanLike | null) => { setAsk({ text, plan, nonce: Date.now() }); setTab("ask"); };
  if (state === "loading") return <main className="mx-auto max-w-5xl px-6 py-10"><p className="text-sm text-zinc-500">Loading…</p></main>;
  if (state === "error") return <main className="mx-auto max-w-5xl px-6 py-10">{back}<p role="alert" className="mt-6 text-sm text-red-600">Could not load this workbook.</p></main>;
  if (state === "notready")
    return <main className="mx-auto max-w-5xl px-6 py-10">{back}<h1 className="mt-6 text-xl font-semibold">{filename}</h1>
      <p className="mt-2 text-sm text-zinc-500">The analysis is not ready yet (status: {status}).</p></main>;

  return (
    <main className="min-h-screen bg-[#f7f8fc]">
      <div className="border-b border-zinc-200/80 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-4 sm:px-8">
          <div className="flex items-center justify-between gap-4">
            {back}
            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-zinc-400 sm:inline">Private workspace</span>
              <ExportReport filename={filename} context={context} charts={charts} facts={facts} insights={insights} guide={guide} />
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-accent">Workbook intelligence</p>
              <h1 className="mt-1 truncate text-2xl font-semibold tracking-tight text-zinc-950 sm:text-3xl">{filename}</h1>
              <p className="mt-1 text-sm text-zinc-500">A decision-ready view of the numbers, patterns, and questions in your workbook.</p>
            </div>
            {context && <div className="hidden rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-right sm:block"><p className="text-xs text-zinc-500">Detected workspace</p><p className="mt-0.5 text-sm font-semibold text-zinc-900">{context.domain.label}</p></div>}
          </div>
        </div>
      </div>
      <div className="mx-auto max-w-7xl px-5 py-6 sm:px-8 sm:py-8">
      <div role="tablist" aria-label="Workbook views" className="flex gap-1 rounded-xl border border-zinc-200 bg-white p-1 shadow-sm">
        {TABS.map((t) => (
          <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:flex-none ${tab === t.id ? "bg-zinc-950 font-medium text-white shadow-sm" : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-7" role="tabpanel">
        {tab === "guide" ? (
          guide ? <GuidePanel guide={guide} charts={charts} workbookId={workbookId} onDetails={() => setTab("details")} onAskTab={() => setTab("ask")} onDone={() => setTab("overview")} />
            : <p className="text-sm text-zinc-500">The guided tour is not available for this file yet. Use the Overview or the Ask tab.</p>
        ) : tab === "ask" ? (
          <div className="space-y-4">
            {userId && <AiConsent userId={userId} enabled={aiOn} onChange={setAiOn} workbookId={workbookId} serverHasAi={serverAi} />}
            <AskPanel workbookId={workbookId} context={context} initial={ask} />
          </div>
        ) : tab === "details" ? <ProfileView workbookId={workbookId} embedded /> : (
          charts.length === 0
            ? <p className="text-sm text-zinc-500">Charts are not available for this file yet. Everything computed from it is under Details.</p>
            : <Dashboard view={tab} tables={tables} columns={columns} charts={charts} facts={facts} findings={findings} onOpenDetails={() => setTab("details")}
              context={context} insights={insights} onAsk={goAsk} onGuide={guide ? () => setTab("guide") : undefined} />
        )}
      </div>
      </div>
    </main>
  );
}
