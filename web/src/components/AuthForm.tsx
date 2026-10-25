"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";

export default function AuthForm({ onBack }: { onBack?: () => void }) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    if (mode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message);
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) setError(error.message);
      else if (!data.session) setNotice("Check your inbox to confirm your email, then sign in.");
    }
    setBusy(false);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,#eef0ff_0%,#fafafa_42%,#fafafa_100%)] px-6 py-10">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-200/80 bg-white/90 p-7 shadow-xl shadow-zinc-900/5 backdrop-blur">
      {onBack && <button type="button" onClick={onBack} className="mb-5 text-sm text-zinc-500 hover:text-zinc-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">← Back to overview</button>}
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-accent">Excel Copilot</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">Understand your spreadsheet.</h1>
      <p className="mt-2 text-sm leading-6 text-zinc-500">Upload your Excel. Get the important numbers, visuals, and next questions.</p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        <label className="block text-sm font-medium">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        </label>

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {notice && <p role="status" className="text-sm text-zinc-600">{notice}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-dark disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        >
          {mode === "signin" ? "Sign in" : "Create account"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null); setNotice(null); }}
        className="mt-4 text-left text-sm text-zinc-500 hover:text-zinc-900"
      >
        {mode === "signin" ? "No account? Create one" : "Already have an account? Sign in"}
      </button>
      </div>
    </main>
  );
}
