"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useGkfyRealtime } from "@/lib/useGkfyRealtime";
import { MarkdownBody } from "@/components/MarkdownBody";
import { stripFrontmatter } from "@/lib/markdown";
import type { Job } from "@/types/job";
import { CancelPendingJobButton } from "@/components/CancelPendingJobButton";
import { RetryFailedJobButton } from "@/components/RetryFailedJobButton";
import { StatusBadge } from "@/components/StatusBadge";
import { JobDetailClient } from "./ui";
import type { GkfyRealtimeMessage } from "@/types/realtime";

export function JobPageClient({ initialJob }: { initialJob: Job }) {
  const [job, setJob] = useState<Job>(initialJob);
  const jobRef = useRef(job);
  jobRef.current = job;

  const resyncFromApi = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/jobs/${initialJob.id}`);
      if (!res.ok) return;
      const row = (await res.json()) as Job;
      setJob(row);
    } catch {
      /* ignore */
    }
  }, [initialJob.id]);

  const onMessage = useCallback(
    (msg: GkfyRealtimeMessage) => {
      if (msg.type === "snapshot" || msg.type === "job_created") return;
      if (msg.type === "job_updated" || msg.type === "job_cancelled") {
        if (msg.data.job.id === initialJob.id) setJob(msg.data.job);
        return;
      }
      if (msg.type === "artifact_updated") {
        const rel = msg.data.rel;
        if (rel && jobRef.current.output_rel_path === rel) void resyncFromApi();
      }
    },
    [initialJob.id, resyncFromApi],
  );

  useGkfyRealtime(onMessage, { onOpen: () => void resyncFromApi() });

  const isPromptJob = job.job_kind === "prompt_generate";
  const promptStem =
    job.output_rel_path?.replace(/^prompts\//, "").replace(/\.md$/i, "") ??
    null;

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/history"
          className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
        >
          ← Historique
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mt-2">
          Job <span className="font-mono text-lg">{job.id}</span>
        </h1>
      </div>

      <dl className="grid sm:grid-cols-2 gap-3 text-sm border border-black/10 dark:border-white/10 rounded-xl p-4">
        <dt className="text-foreground/60">Statut</dt>
        <dd className="space-y-2">
          <StatusBadge status={job.status} />
          {job.status === "pending" ? (
            <CancelPendingJobButton
              jobId={job.id}
              onSuccess={() => void resyncFromApi()}
            />
          ) : null}
          {job.status === "error" ? (
            <RetryFailedJobButton
              jobId={job.id}
              onSuccess={() => void resyncFromApi()}
            />
          ) : null}
        </dd>
        <dt className="text-foreground/60">Type</dt>
        <dd className="text-foreground/80">
          {isPromptJob ? "Génération de prompt (LLM)" : "Ingestion vidéo"}
        </dd>
        {isPromptJob && job.payload?.video_type ? (
          <>
            <dt className="text-foreground/60">Description cible</dt>
            <dd className="text-sm whitespace-pre-wrap">
              {job.payload.video_type}
            </dd>
          </>
        ) : null}
        {isPromptJob &&
        Array.isArray(job.payload?.video_urls) &&
        job.payload.video_urls.length > 0 ? (
          <>
            <dt className="text-foreground/60">Références YouTube</dt>
            <dd>
              <ul className="list-disc pl-5 space-y-1.5 font-mono text-xs break-all">
                {job.payload.video_urls.map((u, i) => (
                  <li key={`${i}-${String(u)}`}>{u}</li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        <dt className="text-foreground/60">
          {isPromptJob ? "Réf. (sentinelle)" : "URL"}
        </dt>
        <dd className="font-mono text-xs break-all">{job.url}</dd>
        {!isPromptJob ? (
          <>
            <dt className="text-foreground/60">Collection</dt>
            <dd>
              {job.playlist_label}
              {job.playlist_auto ? (
                <span className="ml-2 text-xs text-foreground/50">
                  (classée par LLM)
                </span>
              ) : null}
            </dd>
          </>
        ) : null}
        {!isPromptJob && job.playlist_auto ? (
          <>
            <dt className="text-foreground/60">Classifieur</dt>
            <dd className="font-mono text-xs">
              {(job.classifier_provider ?? job.provider) +
                " / " +
                (job.classifier_model ?? job.model)}
            </dd>
          </>
        ) : null}
        <dt className="text-foreground/60">Modèle / thinking</dt>
        <dd>
          {job.model} / {job.thinking_level}
        </dd>
        <dt className="text-foreground/60">Provider</dt>
        <dd>{job.provider}</dd>
        {!isPromptJob ? (
          <>
            <dt className="text-foreground/60">Prompt</dt>
            <dd className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>{job.prompt_name}</span>
              <Link
                href={`/prompts?prompt=${encodeURIComponent(job.prompt_name)}`}
                className="text-sky-600 dark:text-sky-400 underline text-xs shrink-0"
              >
                Ouvrir le prompt
              </Link>
            </dd>
          </>
        ) : null}
        <dt className="text-foreground/60">Fichier</dt>
        <dd className="font-mono text-xs break-all">
          {job.output_rel_path ?? "—"}
        </dd>
        {job.error_message && (
          <>
            <dt className="text-foreground/60">Erreur</dt>
            <dd className="text-red-600 dark:text-red-400 text-xs">
              {job.error_message}
            </dd>
          </>
        )}
        {job.log_message && (
          <>
            <dt className="text-foreground/60">Activité</dt>
            <dd className="font-mono text-xs whitespace-pre-wrap">
              {job.log_message}
            </dd>
          </>
        )}
      </dl>

      {isPromptJob && job.analysis_markdown && promptStem ? (
        <section className="space-y-3">
          <div className="flex flex-wrap gap-3 items-center">
            <h2 className="text-lg font-medium">Prompt généré</h2>
            <a
              className="text-sm text-sky-600 dark:text-sky-400 underline"
              href={`${getApiBase()}/prompts/${encodeURIComponent(promptStem)}`}
              target="_blank"
              rel="noreferrer"
            >
              API JSON (contenu)
            </a>
            <Link
              href="/prompts"
              className="text-sm text-sky-600 dark:text-sky-400 underline"
            >
              Page prompts
            </Link>
          </div>
          <div className="rounded-xl border border-black/10 dark:border-white/10 p-4 max-h-[70vh] overflow-y-auto">
            <MarkdownBody content={stripFrontmatter(job.analysis_markdown)} />
          </div>
        </section>
      ) : null}
      {!isPromptJob && job.output_rel_path ? (
        <section className="space-y-3">
          <div className="flex flex-wrap gap-3 items-center">
            <h2 className="text-lg font-medium">Contenu généré</h2>
            <a
              className="text-sm text-sky-600 dark:text-sky-400 underline"
              href={`${getApiBase()}/artifacts/raw?rel=${encodeURIComponent(job.output_rel_path)}`}
              target="_blank"
              rel="noreferrer"
            >
              Télécharger .md
            </a>
            <Link
              href={`/library?rel=${encodeURIComponent(job.output_rel_path)}`}
              className="text-sm text-sky-600 dark:text-sky-400 underline"
            >
              Ouvrir dans la bibliothèque
            </Link>
          </div>
          <JobDetailClient
            relPath={job.output_rel_path}
            initialMarkdown={job.analysis_markdown}
          />
        </section>
      ) : null}
    </div>
  );
}
