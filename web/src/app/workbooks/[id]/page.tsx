"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import WorkbookView from "@/components/WorkbookView";

export default function WorkbookPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) router.replace("/");
      else setReady(true);
    });
  }, [router]);

  if (!ready) return null;
  return <WorkbookView workbookId={id} />;
}
