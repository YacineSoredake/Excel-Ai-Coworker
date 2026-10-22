"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AiConsent from "@/components/AiConsent";
import AskPanel from "@/components/AskPanel";
import Dashboard, { type ColLite, type FactLite } from "@/components/Dashboard";
import ProfileView from "@/components/ProfileView";
import { supabase } from "@/lib/supabase";
import type { ChartRow, ContextRow, DataTableRow, InsightRow, PlanLike } from "@/lib/types";

type Tab = "overview" | "ask" | "explore" | "details";
const TABS: { id: Tab; label: string }[] = [{ id: "overview", label: "Overview" }, { id: "ask", label: "Ask" }, { id: "explore", label: "Explore" }, { id: "details", label: "Details" }];

export default function WorkbookView({ workbookId }: { workbookId: string }) {
  const [state, setState] = useState<"loading" | "error" | "notready" | "ready">("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState("");
  const [tables, setTables] = useState<DataTableRow[]>([]);
  const [columns, setColumns] = useState<ColLite[]>([]);
  const [charts, setCharts] = useState<ChartRow[]>([]);
  const [facts, setFacts] = useState<FactLite[]>([]);
  const [findings, setFindings] = useState<Record<string, number>>({});
  const [context, setContext] = useState<ContextRow | null>(null);
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
        supabase.from("facts").select("id, table_id, kind, headline, score, payload").eq("workbook_id", workbookId).order("score", { ascending: false }).limit(80),
        supabase.from("workbook_profiles").select("summary, context, analytics").eq("workbook_id", workbookId).single(),
        supabase.from("insights").select("*").eq("workbook_id", workbookId).order("priority"),
        supabase.auth.getUser(),
      ]);
      if (cancelled) return;
      if (t.error || c.error || ch.error || f.error) { setState("error"); return; }
      setTables(t.data as DataTableRow[]);
      setColumns(c.data as ColLite[]);
      setCharts(ch.data as ChartRow[]);
      setFacts(f.data as FactLite[]);
      setFindings((p.data?.summary?.findings_by_severity ?? {}) as Record<string, number>);
      setContext(p.data?.context?.domain ? (p.data.context as ContextRow) : null);
      setInsights((ins.data ?? []) as InsightRow[]);
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
    <main className="mx-auto max-w-5xl px-6 py-8">
      {back}
      <h1 className="mt-4 text-xl font-semibold tracking-tight">{filename}</h1>
      <div role="tablist" aria-label="Workbook views" className="mt-4 flex gap-1 border-b border-zinc-200">
        {TABS.map((t) => (
          <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${tab === t.id ? "border-accent font-medium text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-900"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-6" role="tabpanel">
        {tab === "ask" ? (
          <div className="space-y-4">
            {userId && <AiConsent userId={userId} enabled={aiOn} onChange={setAiOn} workbookId={workbookId} serverHasAi={serverAi} />}
            <AskPanel workbookId={workbookId} context={context} initial={ask} />
          </div>
        ) : tab === "details" ? <ProfileView workbookId={workbookId} embedded /> : (
          charts.length === 0
            ? <p className="text-sm text-zinc-500">Charts are not available for this file yet. Everything computed from it is under Details.</p>
            : <Dashboard view={tab} tables={tables} columns={columns} charts={charts} facts={facts} findings={findings} onOpenDetails={() => setTab("details")}
              context={context} insights={insights} onAsk={goAsk} />
        )}
      </div>
    </main>
  );
}
