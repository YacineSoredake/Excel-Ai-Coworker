"use client";

import { useRef, useState } from "react";
import { supabase } from "@/lib/supabase";
import { BUCKET, MAX_BYTES, XLSX_MIME } from "@/lib/types";

export default function UploadZone({ userId, onUploaded }: { userId: string; onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setError("Only .xlsx files are supported for now. In Excel, use Save As and choose .xlsx.");
      return;
    }
    if (file.size === 0) { setError("This file is empty."); return; }
    if (file.size > MAX_BYTES) { setError("This file is larger than 10 MB."); return; }

    setBusy(true);
    const id = crypto.randomUUID();
    const path = `${userId}/${id}/original.xlsx`;

    const up = await supabase.storage.from(BUCKET).upload(path, file, { contentType: XLSX_MIME, upsert: false });
    if (up.error) {
      setError("Upload failed. Check your connection and try again.");
      setBusy(false);
      return;
    }

    const ins = await supabase
      .from("workbooks")
      .insert({ id, filename: file.name, size_bytes: file.size, storage_path: path });
    if (ins.error) {
      await supabase.storage.from(BUCKET).remove([path]); // don't leave an orphan file
      const message = ins.error.message ?? "";
      setError(/workbook_quota_exceeded/.test(message)
        ? "You have reached the 25-workbook limit for the last 30 days. Delete an older workbook before uploading another."
        : /upload_rate_limited/.test(message)
          ? "You have reached the upload limit. Please try again tomorrow."
          : "Could not register the file. Please try again.");
      setBusy(false);
      return;
    }

    setBusy(false);
    onUploaded();
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void handleFile(f);
  }

  return (
    <section>
      <button
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex w-full flex-col items-center justify-center rounded-lg border border-dashed px-6 py-14 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:opacity-60 ${
          dragging ? "border-accent bg-accent-soft" : "border-zinc-300 bg-white hover:border-zinc-400"
        }`}
      >
        <span className="text-base font-medium">{busy ? "Uploading…" : "Drop an Excel file here"}</span>
        <span className="mt-1 text-sm text-zinc-500">or click to choose a .xlsx file, up to 10 MB</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
          e.target.value = "";
        }}
      />
      {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    </section>
  );
}
