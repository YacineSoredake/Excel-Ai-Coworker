"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import AuthForm from "@/components/AuthForm";
import UploadZone from "@/components/UploadZone";
import WorkbookList from "@/components/WorkbookList";
import ConfirmDialog from "@/components/ConfirmDialog";
import LandingPage from "@/components/LandingPage";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [signingOut, setSigningOut] = useState(false);
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!ready) return null;
  if (!session) return showAuth ? <AuthForm onBack={() => setShowAuth(false)} /> : <LandingPage onGetStarted={() => setShowAuth(true)} />;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#eef0ff_0%,#fafafa_38%,#fafafa_100%)]">
      <div className="mx-auto max-w-4xl px-6 py-8 sm:px-8 sm:py-12">
      <header className="flex items-center justify-between rounded-2xl border border-zinc-200/80 bg-white/80 px-5 py-4 shadow-sm backdrop-blur">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-accent">Excel Copilot</p>
          <h1 className="mt-1 text-lg font-semibold tracking-tight">Your workbooks</h1>
        </div>
        <button
          type="button"
          onClick={() => setSigningOut(true)}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-600 hover:border-zinc-300 hover:text-zinc-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          Sign out
        </button>
      </header>

      <div className="mt-8 space-y-6">
        <section className="rounded-2xl border border-accent/20 bg-white/90 p-6 shadow-sm">
          <p className="text-2xl font-semibold tracking-tight text-zinc-950">Turn a spreadsheet into a clear story.</p>
          <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-600">Upload an Excel workbook and get trusted figures, useful visuals, quality checks, and a guided path through the data.</p>
          <div className="mt-6"><UploadZone userId={session.user.id} onUploaded={() => setRefreshKey((k) => k + 1)} /></div>
        </section>
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-900">Your files</h2>
            <span className="text-xs text-zinc-500">Private to you</span>
          </div>
          <WorkbookList refreshKey={refreshKey} />
        </section>
      </div>
      </div>
      <ConfirmDialog
        open={signingOut}
        title="Sign out of Excel Copilot?"
        description="Your uploaded workbooks stay safely stored. You can sign back in whenever you are ready."
        confirmLabel="Sign out"
        onCancel={() => setSigningOut(false)}
        onConfirm={() => { setSigningOut(false); void supabase.auth.signOut(); }}
      />
    </main>
  );
}
