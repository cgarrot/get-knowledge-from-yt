"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { MarkdownBody } from "@/components/MarkdownBody";

function stripFrontmatter(md: string): string {
  const m = md.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
  return m ? m[1].trim() : md;
}

export function ContentView({ rel }: { rel: string | undefined }) {
  const [body, setBody] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!rel) return;
    let c = false;
    (async () => {
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/artifacts/content?rel=${encodeURIComponent(rel)}`,
        );
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!c) setBody(stripFrontmatter(data.content ?? ""));
      } catch (e) {
        if (!c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      c = true;
    };
  }, [rel]);

  if (!rel) {
    return (
      <p className="text-foreground/70">
        Paramètre <code className="font-mono">rel</code> manquant.
      </p>
    );
  }
  if (err) {
    return <p className="text-red-600 dark:text-red-400">{err}</p>;
  }
  if (body === null) {
    return <p className="text-foreground/50">Chargement…</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/library" className="text-sky-600 dark:text-sky-400 underline">
          Bibliothèque
        </Link>
        <a
          href={`${getApiBase()}/artifacts/raw?rel=${encodeURIComponent(rel)}`}
          className="text-sky-600 dark:text-sky-400 underline"
          target="_blank"
          rel="noreferrer"
        >
          Télécharger
        </a>
      </div>
      <MarkdownBody content={body} />
    </div>
  );
}
