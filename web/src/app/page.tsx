"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import AuthForm from "@/components/AuthForm";
import UploadZone from "@/components/UploadZone";
import WorkbookList from "@/components/WorkbookList";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!ready) return null;
  if (!session) return <AuthForm />;

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Excel Copilot</h1>
        <button
          type="button"
          onClick={() => void supabase.auth.signOut()}
          className="rounded-md px-2 py-1 text-sm text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          Sign out
        </button>
      </header>

      <div className="mt-8 space-y-8">
        <UploadZone userId={session.user.id} onUploaded={() => setRefreshKey((k) => k + 1)} />
        <div>
          <h2 className="mb-3 text-sm font-medium text-zinc-700">Your files</h2>
          <WorkbookList refreshKey={refreshKey} />
        </div>
      </div>
    </main>
  );
}
