"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import FactsSection from "@/components/FactsSection";
import {
  ROLE_LABEL, SEVERITY_LABEL, SEVERITY_ORDER, TYPE_LABEL,
  type ColumnRow, type DataTableRow, type FactRow, type FindingRow, type ProfileRow, type SheetRow, type Severity,
} from "@/lib/types";

const num = (n: number | null | undefined, d = 2) =>
  n == null ? "–" : n.toLocaleString("en-US", { maximumFractionDigits: d });
const pct = (r: number) => (r > 0 && r < 0.005 ? "<1%" : `${Math.round(r * 100)}%`);

const SEV_STYLE: Record<Severity, string> = {
  high: "border-red-300 bg-red-50 text-red-800",
  medium: "border-amber-300 bg-amber-50 text-amber-900",
  low: "border-zinc-300 bg-zinc-50 text-zinc-700",
  info: "border-zinc-200 bg-white text-zinc-500",
};

function columnSummary(c: ColumnRow): string {
  const s = c.stats ?? {};
  switch (c.data_type === "identifier" ? "identifier" : c.data_type) {
    case "integer": case "decimal": case "currency": case "percentage": {
      const unit = c.currency ? ` ${c.currency}` : c.data_type === "percentage" ? "" : "";
      if (c.data_type === "percentage") return `${num((s.min ?? 0) * 100, 1)}% – ${num((s.max ?? 0) * 100, 1)}%`;
      return `${num(s.min)} – ${num(s.max)}${unit} · median ${num(s.median)}`;
    }
    case "date": case "datetime":
      return `${String(s.min ?? "").slice(0, 10)} → ${String(s.max ?? "").slice(0, 10)}${s.granularity ? ` · ${s.granularity}` : ""}`;
    case "boolean": return `${s.true_count ?? 0} yes · ${s.false_count ?? 0} no`;
    default: {
      const top = (s.top_values ?? []).slice(0, 3) as { value: string; count: number }[];
      return top.length ? top.map((t) => `${t.value} (${t.count})`).join(", ") : "–";
    }
  }
}

export default function ProfileView({ workbookId, embedded = false }: { workbookId: string; embedded?: boolean }) {
  const [state, setState] = useState<"loading" | "error" | "notready" | "ready">("loading");
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState("");
  const [profile, setProfile] = useState<ProfileRow | null>(null);
  const [sheets, setSheets] = useState<SheetRow[]>([]);
  const [tables, setTables] = useState<DataTableRow[]>([]);
  const [columns, setColumns] = useState<ColumnRow[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [facts, setFacts] = useState<FactRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const wb = await supabase.from("workbooks").select("filename, status").eq("id", workbookId).single();
      if (cancelled) return;
      if (wb.error || !wb.data) { setState("error"); return; }
      setFilename(wb.data.filename);
      setStatus(wb.data.status);
      if (wb.data.status !== "profiled") { setState("notready"); return; }
      const [p, s, t, c, f, fa] = await Promise.all([
        supabase.from("workbook_profiles").select("summary, relationships, engine_ms, analytics").eq("workbook_id", workbookId).single(),
        supabase.from("sheets").select("*").eq("workbook_id", workbookId).order("position"),
        supabase.from("data_tables").select("*").eq("workbook_id", workbookId).order("position"),
        supabase.from("column_profiles").select("*").eq("workbook_id", workbookId).order("position"),
        supabase.from("findings").select("*").eq("workbook_id", workbookId),
        supabase.from("facts").select("*").eq("workbook_id", workbookId).order("rank"),
      ]);
      if (cancelled) return;
      if (p.error || s.error || t.error || c.error || f.error || fa.error) { setState("error"); return; }
      setProfile(p.data as ProfileRow);
      setSheets(s.data as SheetRow[]);
      setTables(t.data as DataTableRow[]);
      setColumns(c.data as ColumnRow[]);
      setFindings(f.data as FindingRow[]);
      setFacts(fa.data as FactRow[]);
      setState("ready");
    })();
    return () => { cancelled = true; };
  }, [workbookId]);

  const tableName = useMemo(() => Object.fromEntries(tables.map((t) => [t.id, t.name])), [tables]);
  const colName = useMemo(() => Object.fromEntries(columns.map((c) => [c.id, c.name])), [columns]);
  const sorted = useMemo(
    () => [...findings].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)),
    [findings],
  );

  const back = (
    <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
      ← Your files
    </Link>
  );

  if (state === "loading") return <main className="mx-auto max-w-4xl px-6 py-10"><p className="text-sm text-zinc-500">Loading…</p></main>;
  if (state === "error")
    return <main className="mx-auto max-w-4xl px-6 py-10">{back}<p role="alert" className="mt-6 text-sm text-red-600">Could not load this profile.</p></main>;
  if (state === "notready" || !profile)
    return <main className="mx-auto max-w-4xl px-6 py-10">{back}<h1 className="mt-6 text-xl font-semibold">{filename}</h1>
      <p className="mt-2 text-sm text-zinc-500">The profile is not ready yet (status: {status}).</p></main>;

  const sm = profile.summary;
  const counts = SEVERITY_ORDER.filter((s) => sm.findings_by_severity[s] > 0)
    .map((s) => `${sm.findings_by_severity[s]} ${SEVERITY_LABEL[s].toLowerCase()}`).join(" · ");
  const names = (xs: { column: string }[]) => (xs.length ? [...new Set(xs.map((x) => x.column))].join(", ") : "none found");

  return (
    <main className={embedded ? "" : "mx-auto max-w-4xl px-6 py-10"}>
      {!embedded && back}
      {!embedded && <h1 className="mt-6 text-xl font-semibold tracking-tight">{filename}</h1>}

      <section aria-labelledby="understanding" className="rounded-lg border border-zinc-200 bg-white p-5">
        <h2 id="understanding" className="text-sm font-medium text-zinc-700">What we found</h2>
        <p className="mt-2 text-base">
          {sm.table_count} table{sm.table_count === 1 ? "" : "s"} across {sm.sheet_count} sheet{sm.sheet_count === 1 ? "" : "s"},
          {" "}{num(sm.total_rows, 0)} data rows.
        </p>
        <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-x-4 gap-y-1.5 text-sm">
          <dt className="text-zinc-500">Measures</dt><dd>{names(sm.measures)}</dd>
          <dt className="text-zinc-500">Dimensions</dt><dd>{names(sm.dimensions)}</dd>
          <dt className="text-zinc-500">Identifiers</dt><dd>{names(sm.identifiers)}</dd>
          <dt className="text-zinc-500">Time</dt>
          <dd>{sm.time.length ? sm.time.map((t) => `${t.column}: ${String(t.min).slice(0, 10)} → ${String(t.max).slice(0, 10)}${t.granularity ? ` (${t.granularity})` : ""}`).join("; ") : "no date column found"}</dd>
        </dl>
      </section>

      <FactsSection facts={facts} analyticsError={profile.analytics?.error} />

      <section aria-labelledby="issues" className="mt-8">
        <h2 id="issues" className="text-sm font-medium text-zinc-700">
          Potential issues {counts ? <span className="font-normal text-zinc-500">· {counts}</span> : null}
        </h2>
        <p className="mt-1 text-sm text-zinc-500">These are signals to check, not confirmed errors. Nothing in your file was changed.</p>
        {sorted.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-500">No issues found.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {sorted.map((f) => (
              <li key={f.id} className="rounded-lg border border-zinc-200 bg-white p-4">
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-xs font-medium ${SEV_STYLE[f.severity]}`}>
                    {SEVERITY_LABEL[f.severity]}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{f.title}</p>
                    {f.detail && <p className="mt-1 text-sm text-zinc-600">{f.detail}</p>}
                    <p className="mt-1.5 text-xs text-zinc-500">
                      {[f.table_id ? tableName[f.table_id] : null, f.column_id ? colName[f.column_id] : null]
                        .filter(Boolean).join(" › ")}
                      {f.affected_count != null && f.total_count != null ? ` · ${f.affected_count} of ${f.total_count} rows` : ""}
                      {f.sample_rows.length ? ` · Excel rows ${f.sample_rows.join(", ")}${(f.affected_count ?? 0) > f.sample_rows.length ? "…" : ""}` : ""}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="tables" className="mt-10">
        <h2 id="tables" className="text-sm font-medium text-zinc-700">Tables and columns</h2>
        <div className="mt-3 space-y-6">
          {tables.map((t) => (
            <div key={t.id} className="rounded-lg border border-zinc-200 bg-white">
              <div className="border-b border-zinc-200 px-4 py-3">
                <h3 className="text-sm font-semibold">{t.name}</h3>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {t.cell_range} · {num(t.row_count, 0)} rows × {t.column_count} columns · header row {t.header_row ?? "not found"}
                  {" "}· detection confidence {pct(t.confidence)}{t.source === "excel_table" ? " · defined as a table in Excel" : ""}
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[40rem] text-left text-sm">
                  <thead className="text-xs text-zinc-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Column</th><th className="px-2 py-2 font-medium">Type</th>
                      <th className="px-2 py-2 font-medium">Role</th><th className="px-2 py-2 font-medium">Missing</th>
                      <th className="px-2 py-2 font-medium">Distinct</th><th className="px-4 py-2 font-medium">Summary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {columns.filter((c) => c.table_id === t.id).map((c) => (
                      <tr key={c.id}>
                        <td className="px-4 py-2 font-medium">{c.name}</td>
                        <td className="px-2 py-2">{TYPE_LABEL[c.data_type] ?? c.data_type}{c.currency ? ` · ${c.currency}` : ""}</td>
                        <td className="px-2 py-2">
                          {ROLE_LABEL[c.role] ?? c.role}{c.role_subtype ? ` · ${c.role_subtype.replace("_", " ")}` : ""}
                          {(c.role_confidence ?? 1) < 0.7 && <span className="ml-1 text-xs text-zinc-500">(unsure)</span>}
                        </td>
                        <td className="px-2 py-2">{c.missing_count ? `${c.missing_count} (${pct(c.missing_rate)})` : "–"}</td>
                        <td className="px-2 py-2">{num(c.distinct_count, 0)}</td>
                        <td className="px-4 py-2 text-zinc-600">{columnSummary(c)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {tables.length === 0 && <p className="text-sm text-zinc-500">No data tables were found in this workbook.</p>}
        </div>
      </section>

      {profile.relationships.length > 0 && (
        <section aria-labelledby="rels" className="mt-10">
          <h2 id="rels" className="text-sm font-medium text-zinc-700">Links between tables</h2>
          <ul className="mt-3 space-y-1.5 text-sm">
            {profile.relationships.map((r, i) => (
              <li key={i} className="rounded-lg border border-zinc-200 bg-white px-4 py-2.5">
                <span className="font-medium">{r.from_table_name} › {r.from_column}</span> looks like a reference to{" "}
                <span className="font-medium">{r.to_table_name} › {r.to_column}</span>
                <span className="text-zinc-500"> · {pct(r.containment)} of values match · confidence {pct(r.confidence)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="sheets" className="mt-10">
        <h2 id="sheets" className="text-sm font-medium text-zinc-700">Sheets</h2>
        <ul className="mt-3 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white text-sm">
          {sheets.map((s) => (
            <li key={s.id} className="px-4 py-3">
              <p className="font-medium">{s.name}{s.hidden ? <span className="ml-2 text-xs font-normal text-zinc-500">hidden</span> : null}</p>
              <p className="mt-0.5 text-xs text-zinc-500">
                {s.is_empty ? "Empty" : `${num(s.row_count, 0)} rows × ${s.column_count} columns`}
                {s.formula_count ? ` · ${s.formula_count} formulas` : ""}{s.merged_count ? ` · ${s.merged_count} merged areas` : ""}
              </p>
              {s.notes.length > 0 && <p className="mt-1 text-xs text-zinc-500">Notes above the data: {s.notes.slice(0, 3).join(" · ")}</p>}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
