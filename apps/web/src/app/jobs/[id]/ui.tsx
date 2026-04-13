"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { MarkdownBody } from "@/components/MarkdownBody";

function stripFrontmatter(md: string): string {
  const m = md.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
  return m ? m[1].trim() : md;
}

export function JobDetailClient({
  relPath,
  initialMarkdown,
}: {
  relPath: string;
  /** Copie persistée en base (évite un aller-retour disque/API). */
  initialMarkdown?: string | null;
}) {
  const [body, setBody] = useState<string | null>(() =>
    initialMarkdown
      ? stripFrontmatter(initialMarkdown)
      : null,
  );
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (initialMarkdown) return;
    let cancelled = false;
    (async () => {
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/artifacts/content?rel=${encodeURIComponent(relPath)}`,
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
  }, [relPath, initialMarkdown]);

  if (err) {
    return <p className="text-sm text-red-600 dark:text-red-400">{err}</p>;
  }
  if (body === null) {
    return <p className="text-sm text-foreground/50">Chargement du markdown…</p>;
  }
  return (
    <div className="rounded-xl border border-black/10 dark:border-white/10 p-4 max-h-[70vh] overflow-y-auto">
      <MarkdownBody content={body} />
    </div>
  );
}
