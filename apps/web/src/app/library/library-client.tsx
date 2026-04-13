"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useGkfyRealtime } from "@/lib/useGkfyRealtime";
import { ArticleReader } from "@/components/ArticleReader";

interface Playlist {
  name: string;
  files: string[];
}

export function LibraryClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rel = searchParams.get("rel") ?? undefined;

  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [mobileTreeOpen, setMobileTreeOpen] = useState(false);
  const [readerTick, setReaderTick] = useState(0);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/artifacts/tree`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setPlaylists(data.playlists ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useGkfyRealtime(
    useCallback((msg) => {
      if (msg.type === "artifact_updated") {
        void load();
        setReaderTick((t) => t + 1);
        return;
      }
      if (msg.type === "job_updated" || msg.type === "job_cancelled") {
        const st = msg.data.job.status;
        if (st === "ok" || st === "skipped" || st === "error") void load();
      }
    }, [load]),
    { onOpen: () => void load() },
  );

  const base = getApiBase();

  const selectRel = (path: string) => {
    router.replace(`/library?rel=${encodeURIComponent(path)}`, {
      scroll: false,
    });
    setMobileTreeOpen(false);
  };

  return (
    <div className="flex flex-col rounded-xl border border-black/10 dark:border-white/10 overflow-hidden min-h-[calc(100vh-7rem)] -mx-4 sm:mx-0">
      <div className="shrink-0 border-b border-black/10 dark:border-white/10 px-4 py-3 flex flex-wrap items-center gap-3 justify-between gap-y-2 bg-background">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">Bibliothèque</h1>
          <p className="text-xs text-foreground/60 mt-0.5 max-w-xl">
            Analyses (base et{" "}
            <code className="font-mono text-[0.7rem]">data/output</code> si{" "}
            <code className="font-mono text-[0.7rem]">GKFY_WRITE_OUTPUT_FILES</code>
            ).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="md:hidden rounded-lg border border-black/15 dark:border-white/15 px-3 py-1.5 text-sm"
            onClick={() => setMobileTreeOpen((o) => !o)}
            aria-expanded={mobileTreeOpen}
          >
            {mobileTreeOpen ? "Masquer fichiers" : "Fichiers"}
          </button>
          <a
            href={`${base}/artifacts/zip`}
            className="rounded-lg bg-foreground text-background px-3 py-1.5 text-sm font-medium"
          >
            ZIP tout
          </a>
          <button
            type="button"
            onClick={() => load()}
            className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-1.5 text-sm"
          >
            Rafraîchir
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 flex-col md:flex-row">
        <aside
          className={[
            "shrink-0 flex flex-col border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.02]",
            "md:w-64 md:border-r md:max-h-none md:flex",
            mobileTreeOpen ? "flex max-h-[min(50vh,22rem)] border-b" : "hidden",
          ].join(" ")}
        >
          <div className="overflow-y-auto flex-1 p-2">
            {err && (
              <p className="text-xs text-red-600 dark:text-red-400 px-2 py-1">
                {err}
              </p>
            )}
            {playlists.map((pl) => {
              const folderPath = pl.name === "." ? "" : pl.name;
              const title = folderPath || "(racine)";
              return (
                <details
                  key={pl.name}
                  className="group border-b border-black/5 dark:border-white/5 last:border-0"
                  open
                >
                  <summary className="cursor-pointer list-none flex items-center justify-between gap-2 py-2 px-2 rounded-md hover:bg-black/5 dark:hover:bg-white/10 text-sm font-medium">
                    <span className="truncate" title={title}>
                      {title}
                    </span>
                    <a
                      href={`${base}/artifacts/zip?playlist=${encodeURIComponent(pl.name)}`}
                      className="shrink-0 text-[0.65rem] text-sky-600 dark:text-sky-400 underline font-normal"
                      onClick={(e) => e.stopPropagation()}
                    >
                      ZIP
                    </a>
                  </summary>
                  <ul className="pb-2 space-y-0.5 pl-1">
                    {pl.files.map((f) => {
                      const path = folderPath ? `${folderPath}/${f}` : f;
                      const active = path === rel;
                      return (
                        <li key={path}>
                          <button
                            type="button"
                            onClick={() => selectRel(path)}
                            className={[
                              "w-full text-left rounded-md px-2 py-1.5 text-xs transition-colors",
                              active
                                ? "bg-sky-500/20 text-sky-800 dark:text-sky-200 font-medium"
                                : "text-foreground/80 hover:bg-black/5 dark:hover:bg-white/10",
                            ].join(" ")}
                          >
                            <span className="font-mono break-all">{f}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  {pl.files.length === 0 && (
                    <p className="text-xs text-foreground/45 px-2 pb-2">
                      Aucun fichier.
                    </p>
                  )}
                </details>
              );
            })}
            {playlists.length === 0 && !err && (
              <p className="text-foreground/50 text-xs px-2 py-2">
                Aucune playlist. Lancez des jobs depuis l’accueil.
              </p>
            )}
          </div>
        </aside>

        <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden bg-background">
          <ArticleReader
            rel={rel}
            libraryContext
            contentVersion={readerTick}
          />
        </div>
      </div>
    </div>
  );
}
