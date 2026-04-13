import Link from "next/link";
import { getApiBase, getServerApiBase } from "@/lib/api";
import type { Job } from "@/types/job";
import { StatusBadge } from "@/components/StatusBadge";
import { JobDetailClient } from "./ui";

async function fetchJob(id: string): Promise<Job | null> {
  const base = getServerApiBase();
  const res = await fetch(`${base}/jobs/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const job = await fetchJob(id);
  if (!job) {
    return (
      <div className="space-y-4">
        <p>Job introuvable.</p>
        <Link href="/" className="text-sky-600 dark:text-sky-400 underline">
          Retour
        </Link>
      </div>
    );
  }

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
        <dd>
          <StatusBadge status={job.status} />
        </dd>
        <dt className="text-foreground/60">URL</dt>
        <dd className="font-mono text-xs break-all">{job.url}</dd>
        <dt className="text-foreground/60">Collection</dt>
        <dd>
          {job.playlist_label}
          {job.playlist_auto ? (
            <span className="ml-2 text-xs text-foreground/50">(classée par LLM)</span>
          ) : null}
        </dd>
        {job.playlist_auto ? (
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
        <dt className="text-foreground/60">Prompt</dt>
        <dd>{job.prompt_name}</dd>
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
            <dt className="text-foreground/60">Log</dt>
            <dd className="font-mono text-xs">{job.log_message}</dd>
          </>
        )}
      </dl>

      {job.output_rel_path && (
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
              href={`/content?rel=${encodeURIComponent(job.output_rel_path)}`}
              className="text-sm text-sky-600 dark:text-sky-400 underline"
            >
              Vue pleine page
            </Link>
          </div>
          <JobDetailClient
            relPath={job.output_rel_path}
            initialMarkdown={job.analysis_markdown}
          />
        </section>
      )}
    </div>
  );
}
