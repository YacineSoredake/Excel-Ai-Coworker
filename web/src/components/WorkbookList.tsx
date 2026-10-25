"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { ARTIFACTS, BUCKET, formatSize, type Workbook } from "@/lib/types";
import ConfirmDialog from "@/components/ConfirmDialog";

const PENDING = new Set(["uploaded", "validating", "validated", "analyzing"]);

function statusText(w: Workbook): string {
  switch (w.status) {
    case "uploaded": return "Waiting to be checked";
    case "validating": return "Checking the file…";
    case "validated": return "File checked, starting analysis…";
    case "analyzing": return "Analyzing the data…";
    case "profiled": {
      const n = w.sheet_count ?? 0;
      return `Ready · ${n} sheet${n === 1 ? "" : "s"}`;
    }
    case "rejected":
    case "failed": return w.rejection_reason ?? "This file could not be processed.";
  }
}

async function removeFolder(bucket: string, prefix: string): Promise<void> {
  const store = supabase.storage.from(bucket);
  const { data } = await store.list(prefix, { limit: 1000 });
  if (!data) return;
  for (const folder of data.filter((i) => !i.id)) await removeFolder(bucket, `${prefix}/${folder.name}`);
  const files = data.filter((i) => i.id).map((i) => `${prefix}/${i.name}`);
  if (files.length) await store.remove(files);
}

export default function WorkbookList({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<Workbook[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Workbook | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    const { data, error } = await supabase
      .from("workbooks")
      .select("id, filename, size_bytes, status, sheet_count, hidden_sheets, has_external_links, rejection_reason, created_at")
      .order("created_at", { ascending: false });
    if (error) setError("Could not load your files.");
    else { setError(null); setItems(data as Workbook[]); }
  }, []);

  useEffect(() => { void load(); }, [load, refreshKey]);

  useEffect(() => {
    if (!items?.some((w) => PENDING.has(w.status))) return;
    const t = setInterval(() => void load(), 2000);
    return () => clearInterval(t);
  }, [items, load]);

  async function onDelete(w: Workbook) {
    setDeleting(true);
    const { data } = await supabase.auth.getUser();
    if (!data.user) { setDeleting(false); return; }
    const prefix = `${data.user.id}/${w.id}`;
    await removeFolder(BUCKET, prefix);
    await removeFolder(ARTIFACTS, prefix);
    const { error } = await supabase.from("workbooks").delete().eq("id", w.id); // profile rows cascade
    if (error) {
      setError("Could not delete this workbook. Please try again.");
      setDeleting(false);
      return;
    }
    setDeleting(false);
    setPendingDelete(null);
    void load();
  }

  if (error) return <p role="alert" className="text-sm text-red-600">{error}</p>;
  if (items === null) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (items.length === 0) return <p className="text-sm text-zinc-500">No files yet. Upload one to get started.</p>;

  return (
    <>
      <ul className="divide-y divide-zinc-200 rounded-2xl border border-zinc-200/80 bg-white/90 shadow-sm">
      {items.map((w) => {
        const bad = w.status === "rejected" || w.status === "failed";
        return (
          <li key={w.id} className="flex items-center justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{w.filename}</p>
              <p className={`mt-0.5 text-sm ${bad ? "text-red-600" : "text-zinc-500"}`}>
                {statusText(w)} · {formatSize(w.size_bytes)}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {w.status === "profiled" && (
                <Link
                  href={`/workbooks/${w.id}`}
                  className="rounded-md px-2 py-1 text-sm font-medium text-accent hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  Open dashboard
                </Link>
              )}
              <button
                type="button"
                onClick={() => setPendingDelete(w)}
                className="rounded-lg px-2 py-1.5 text-sm text-zinc-500 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                Delete
              </button>
            </div>
          </li>
        );
      })}
      </ul>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this workbook permanently?"
        description={pendingDelete ? `"${pendingDelete.filename}" and its analyzed data, charts, insights, and cleaned tables will be removed. This cannot be undone.` : ""}
        confirmLabel="Delete workbook"
        destructive
        busy={deleting}
        onCancel={() => { if (!deleting) setPendingDelete(null); }}
        onConfirm={() => { if (pendingDelete) void onDelete(pendingDelete); }}
      />
    </>
  );
}
