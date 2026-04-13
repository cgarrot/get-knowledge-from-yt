"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { JobKind } from "@/types/job";
import { getApiBase } from "@/lib/api";
import { stripFrontmatter } from "@/lib/markdown";
import { MarkdownBody } from "@/components/MarkdownBody";
import { ReadingOutline } from "@/components/ReadingOutline";

export function ArticleReader({
  rel,
  /** Bumps when the same `rel` should be re-fetched (e.g. live artifact update). */
  contentVersion = 0,
  /** When true, show a compact toolbar (library link, raw download). */
  showToolbar = true,
  /** Three-column layout: reader + outline (library). When false, single column (e.g. job preview). */
  showOutline = true,
  /** Hide "Bibliothèque" in toolbar when already on the library page. */
  libraryContext = false,
}: {
  rel: string | undefined;
  contentVersion?: number;
  showToolbar?: boolean;
  showOutline?: boolean;
  libraryContext?: boolean;
}) {
  const articleRef = useRef<HTMLElement | null>(null);
  const [body, setBody] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sourceJob, setSourceJob] = useState<{
    id: string;
    prompt_name: string;
    job_kind: JobKind;
  } | null>(null);

  useEffect(() => {
    if (!rel) return;
    let cancelled = false;
    setErr(null);
    setBody(null);
    (async () => {
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/artifacts/content?rel=${encodeURIComponent(rel)}`,
        );
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!cancelled) setBody(stripFrontmatter(data.content ?? ""));
      } catch (e) {
        if (!cancelled)
          setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
   }, [rel, contentVersion]);

  useEffect(() => {
    if (!rel) {
      setSourceJob(null);
      return;
    }
    let cancelled = false;
    setSourceJob(null);
    (async () => {
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/jobs/by-output?rel=${encodeURIComponent(rel)}`,
        );
        if (res.status === 404) return;
        if (!res.ok) return;
        const data = (await res.json()) as {
          id?: string;
          prompt_name?: string;
          job_kind?: JobKind;
        };
        if (
          cancelled ||
          !data.id ||
          typeof data.prompt_name !== "string" ||
          !data.prompt_name
        ) {
          return;
        }
        setSourceJob({
          id: data.id,
          prompt_name: data.prompt_name,
          job_kind: data.job_kind ?? "video",
        });
      } catch {
        /* ignore: optional metadata */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rel, contentVersion]);

  if (!rel) {
    return (
      <p className="text-foreground/70 text-sm">
        Sélectionnez un fichier dans la liste ou ouvrez un lien avec{" "}
        <code className="font-mono text-xs">?rel=</code>.
      </p>
    );
  }
  if (err) {
    return <p className="text-sm text-red-600 dark:text-red-400">{err}</p>;
  }
  if (body === null) {
    return <p className="text-foreground/50 text-sm">Chargement…</p>;
  }

  const parts = rel.split("/");
  const fileName = parts[parts.length - 1] || rel;
  const folder =
    parts.length > 1 ? parts.slice(0, -1).join("/") : null;

  const showPromptUsedLink =
    sourceJob &&
    sourceJob.job_kind !== "prompt_generate" &&
    sourceJob.prompt_name !== "_prompt_generate_";

  const readerColumn = (
    <div className="min-w-0 flex-1 overflow-y-auto px-4 py-4 md:px-6 md:py-6">
      {showToolbar && (
        <div className="flex flex-wrap gap-3 text-sm mb-4">
          {!libraryContext && (
            <Link
              href="/library"
              className="text-sky-600 dark:text-sky-400 underline"
            >
              Bibliothèque
            </Link>
          )}
          {showPromptUsedLink ? (
            <Link
              href={`/prompts?prompt=${encodeURIComponent(sourceJob.prompt_name)}`}
              className="text-sky-600 dark:text-sky-400 underline"
            >
              Prompt utilisé
            </Link>
          ) : null}
          {sourceJob ? (
            <Link
              href={`/jobs/${sourceJob.id}`}
              className="text-sky-600 dark:text-sky-400 underline"
            >
              Job source
            </Link>
          ) : null}
          <a
            href={`${getApiBase()}/artifacts/raw?rel=${encodeURIComponent(rel)}`}
            className="text-sky-600 dark:text-sky-400 underline"
            target="_blank"
            rel="noreferrer"
          >
            Télécharger .md
          </a>
        </div>
      )}
      {(folder || fileName) && (
        <p className="text-xs text-foreground/50 font-mono mb-3 break-all">
          {folder ? (
            <>
              <span>{folder}</span>
              <span className="text-foreground/35"> / </span>
            </>
          ) : null}
          <span className="text-foreground/70">{fileName}</span>
        </p>
      )}
      <MarkdownBody ref={articleRef} content={body} />
    </div>
  );

  if (!showOutline) {
    return readerColumn;
  }

  return (
    <div className="flex flex-col lg:flex-row flex-1 min-h-0 min-w-0">
      {readerColumn}
      <aside className="hidden lg:block w-52 shrink-0 border-l border-black/10 dark:border-white/10 px-3 py-6 overflow-y-auto">
        <ReadingOutline articleRef={articleRef} contentVersion={body} />
      </aside>
      <div className="lg:hidden border-t border-black/10 dark:border-white/10 px-4 py-3 bg-black/[0.02] dark:bg-white/[0.02] shrink-0">
        <ReadingOutline articleRef={articleRef} contentVersion={body} />
      </div>
    </div>
  );
}
