"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import {
  JOB_ACTIVITY_TRUNC,
  recentJobUrlSummary,
} from "@/lib/jobTableDisplay";
import { useGkfyRealtime } from "@/lib/useGkfyRealtime";
import type { Job, JobStatus } from "@/types/job";
import { StatusBadge } from "@/components/StatusBadge";
import { CancelPendingJobButton } from "@/components/CancelPendingJobButton";

const STATUSES: (JobStatus | "")[] = [
  "",
  "pending",
  "processing",
  "cancelled",
  "ok",
  "error",
  "skipped",
];

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filter, setFilter] = useState<JobStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const base = getApiBase();
      const q = filter ? `?limit=500&status=${encodeURIComponent(filter)}` : "?limit=500";
      const res = await fetch(`${base}/jobs${q}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setJobs(data.jobs ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const loadRef = useRef(load);
  loadRef.current = load;
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useGkfyRealtime(
    useCallback((msg) => {
      if (
        msg.type === "job_created" ||
        msg.type === "job_updated" ||
        msg.type === "job_cancelled"
      ) {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
          debounceRef.current = null;
          void loadRef.current();
        }, 250);
      }
    }, []),
    { onOpen: () => void loadRef.current() },
  );

  const sorted = useMemo(
    () => [...jobs].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [jobs],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Historique</h1>
          <p className="text-sm text-foreground/70 mt-1">
            Tous les jobs persistés en SQLite côté API.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-foreground/70">Filtrer</label>
          <select
            className="rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
            value={filter}
            onChange={(e) =>
              setFilter((e.target.value || "") as JobStatus | "")
            }
          >
            {STATUSES.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "tous"}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => load()}
            className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm"
          >
            Rafraîchir
          </button>
        </div>
      </div>

      {err && (
        <p className="text-sm text-red-600 dark:text-red-400">{err}</p>
      )}

      <div className="rounded-xl border border-black/10 dark:border-white/10 overflow-x-auto">
        {loading ? (
          <p className="p-6 text-sm text-foreground/50">Chargement…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/10 dark:border-white/10 text-left text-foreground/60">
                <th className="p-3 font-medium">Créé</th>
                <th className="p-3 font-medium">Statut</th>
                <th className="p-3 font-medium">URL</th>
                <th className="p-3 font-medium max-w-[240px]">Activité</th>
                <th className="p-3 font-medium">Collection</th>
                <th className="p-3 font-medium">Prompt</th>
                <th className="p-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((j) => (
                <tr
                  key={j.id}
                  className="border-b border-black/5 dark:border-white/5"
                >
                  <td className="p-3 whitespace-nowrap font-mono text-xs">
                    {new Date(j.created_at).toLocaleString()}
                  </td>
                  <td className="p-3">
                    <StatusBadge status={j.status} />
                  </td>
                  <td
                    className="p-3 max-w-[220px] truncate font-mono text-xs"
                    title={recentJobUrlSummary(j)}
                  >
                    {recentJobUrlSummary(j)}
                  </td>
                  <td
                    className="p-3 max-w-[240px] font-mono text-xs text-foreground/80"
                    title={j.log_message ?? undefined}
                  >
                    {j.log_message ? (
                      <span className="line-clamp-2 break-words">
                        {j.log_message.length > JOB_ACTIVITY_TRUNC
                          ? `${j.log_message.slice(0, JOB_ACTIVITY_TRUNC - 1)}…`
                          : j.log_message}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3">{j.playlist_label}</td>
                  <td className="p-3">{j.prompt_name}</td>
                  <td className="p-3 whitespace-nowrap">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/jobs/${j.id}`}
                        className="text-sky-600 dark:text-sky-400 hover:underline"
                      >
                        Détail
                      </Link>
                      {j.status === "pending" ? (
                        <CancelPendingJobButton
                          jobId={j.id}
                          onSuccess={() => void load()}
                          label="Retirer de la file"
                        />
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && sorted.length === 0 && (
          <p className="p-6 text-foreground/50 text-sm">Aucun job.</p>
        )}
      </div>
    </div>
  );
}
