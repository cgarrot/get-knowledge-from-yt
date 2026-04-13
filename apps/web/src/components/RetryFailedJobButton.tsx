"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { getApiBase } from "@/lib/api";

export function RetryFailedJobButton({
  jobId,
  onSuccess,
  className = "",
  label = "Relancer",
}: {
  jobId: string;
  onSuccess?: () => void;
  className?: string;
  label?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onRetry() {
    setErr(null);
    setBusy(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/jobs/${jobId}/retry`, {
        method: "POST",
      });
      if (!res.ok) {
        let msg = res.statusText;
        try {
          const data = await res.json();
          if (typeof data?.detail === "string") msg = data.detail;
        } catch {
          const t = await res.text();
          if (t) msg = t;
        }
        throw new Error(msg);
      }
      onSuccess?.();
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const btn =
    "rounded-lg border border-black/15 dark:border-white/15 px-2.5 py-1 text-xs font-medium text-foreground/90 hover:bg-black/[0.04] dark:hover:bg-white/[0.06] disabled:opacity-50 disabled:pointer-events-none transition-colors";

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        disabled={busy}
        onClick={onRetry}
        className={`${btn} ${className}`.trim()}
      >
        {busy ? "…" : label}
      </button>
      {err ? (
        <span className="text-xs text-red-600 dark:text-red-400 max-w-[220px]">
          {err}
        </span>
      ) : null}
    </span>
  );
}
