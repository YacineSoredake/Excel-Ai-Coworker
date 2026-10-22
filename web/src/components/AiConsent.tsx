"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";

/** AI is opt-in. The disclosure states exactly what leaves the server (report §15). */
export default function AiConsent({ userId, enabled, onChange, workbookId, serverHasAi }: {
  userId: string; enabled: boolean; onChange: (v: boolean) => void; workbookId: string; serverHasAi: boolean | null;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function toggle(v: boolean) {
    setBusy(true); setMsg(null);
    const { error } = await supabase.from("user_settings").upsert({ user_id: userId, ai_enabled: v, ai_consent_at: v ? new Date().toISOString() : null, updated_at: new Date().toISOString() });
    if (error) setMsg("Could not save this setting."); else onChange(v);
    setBusy(false);
  }
  async function rewrite() {
    setBusy(true);
    const { error } = await supabase.rpc("request_reanalysis", { p_workbook: workbookId });
    setMsg(error ? "Could not start the rewrite." : "Re-analysing. The insights will be rewritten in a minute: reopen the Overview.");
    setBusy(false);
  }

  return (
    <section aria-labelledby="ai" className="rounded-lg border border-zinc-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="ai" className="text-sm font-semibold">AI assistance</h2>
          <p className="mt-1 text-sm text-zinc-600">
            {enabled ? "On. AI helps understand your questions and words the answers. You can turn it off at any time."
              : "Off. Questions and summaries use built-in logic. Turn AI on to ask in your own words and get fuller wording."}
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm">
          <input type="checkbox" role="switch" checked={enabled} disabled={busy} onChange={(e) => void toggle(e.target.checked)} />
          <span>{enabled ? "On" : "Off"}</span>
        </label>
      </div>
      <details className="mt-3 text-xs text-zinc-600" open={!enabled}>
        <summary className="cursor-pointer text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">What is sent to the AI provider</summary>
        <ul className="mt-1.5 list-disc space-y-1 pl-4">
          <li><span className="font-medium">Sent:</span> your question, column names, the names of categories (for example product or region names), and figures already computed from your data (totals, rankings, changes).</li>
          <li><span className="font-medium">Never sent:</span> your spreadsheet rows, people&apos;s names, free-text columns, or the file itself.</li>
          <li>The AI never calculates. Every number in an answer is computed by this app and checked again; wording that fails the check is replaced by built-in wording.</li>
          <li>Your AI provider&apos;s own terms apply to what it receives. Free tiers of some providers may use inputs to improve their products, so check the terms of the provider this app is configured with.</li>
        </ul>
      </details>
      {enabled && serverHasAi === false && <p className="mt-2 text-xs text-amber-900">No AI provider is configured on this server, so built-in logic is still being used.</p>}
      {enabled && (
        <button type="button" onClick={() => void rewrite()} disabled={busy}
          className="mt-3 rounded-md border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
          Rewrite this workbook&apos;s insights with AI
        </button>
      )}
      {msg && <p role="status" className="mt-2 text-xs text-zinc-600">{msg}</p>}
    </section>
  );
}
