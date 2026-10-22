"use client";

import { useCallback, useRef, useState } from "react";
import { supabase } from "@/lib/supabase";
import { readTable, type Row } from "@/lib/dataEngine";
import { ARTIFACTS, type DataTableRow } from "@/lib/types";

export type LoadState = "idle" | "loading" | "error";

/** Loads the cleaned table (Parquet) only when something needs it: a filter, or a drill-down. */
export function useTableRows() {
  const cache = useRef(new Map<string, Row[]>());
  const [state, setState] = useState<Record<string, LoadState>>({});

  const ensure = useCallback(async (t: DataTableRow): Promise<Row[] | null> => {
    const hit = cache.current.get(t.id);
    if (hit) return hit;
    if (!t.artifact_path) { setState((s) => ({ ...s, [t.id]: "error" })); return null; }
    setState((s) => ({ ...s, [t.id]: "loading" }));
    try {
      const { data, error } = await supabase.storage.from(ARTIFACTS).download(t.artifact_path);
      if (error || !data) throw error ?? new Error("empty");
      const rows = await readTable(await data.arrayBuffer());
      cache.current.set(t.id, rows);
      setState((s) => ({ ...s, [t.id]: "idle" }));
      return rows;
    } catch {
      setState((s) => ({ ...s, [t.id]: "error" }));
      return null;
    }
  }, []);

  return { ensure, rowsOf: (id: string) => cache.current.get(id) ?? null, state };
}
