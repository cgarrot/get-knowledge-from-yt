"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

interface Playlist {
  name: string;
  files: string[];
}

export default function LibraryPage() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [err, setErr] = useState<string | null>(null);

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

  const base = getApiBase();

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bibliothèque</h1>
          <p className="text-sm text-foreground/70 mt-1">
            Analyses depuis la base (et fichiers sous <code className="font-mono text-xs">data/output</code>{" "}
            si l’API exporte avec <code className="font-mono text-xs">GKFY_WRITE_OUTPUT_FILES</code>).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={`${base}/artifacts/zip`}
            className="rounded-lg bg-foreground text-background px-3 py-2 text-sm font-medium"
          >
            ZIP tout
          </a>
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

      <div className="space-y-6">
        {playlists.map((pl) => {
          const folderPath = pl.name === "." ? "" : pl.name;
          const title = folderPath || "(racine)";
          return (
          <section
            key={pl.name}
            className="rounded-xl border border-black/10 dark:border-white/10 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h2 className="font-medium break-all">{title}</h2>
              <a
                href={`${base}/artifacts/zip?playlist=${encodeURIComponent(pl.name)}`}
                className="text-sm text-sky-600 dark:text-sky-400 underline"
              >
                Télécharger ZIP
              </a>
            </div>
            <ul className="text-sm space-y-1 font-mono">
              {pl.files.map((f) => {
                const rel = folderPath ? `${folderPath}/${f}` : f;
                return (
                  <li key={rel} className="flex flex-wrap gap-2 items-center">
                    <span className="text-foreground/80">{f}</span>
                    <Link
                      href={`/content?rel=${encodeURIComponent(rel)}`}
                      className="text-sky-600 dark:text-sky-400 text-xs underline"
                    >
                      lire
                    </Link>
                    <a
                      href={`${base}/artifacts/raw?rel=${encodeURIComponent(rel)}`}
                      className="text-sky-600 dark:text-sky-400 text-xs underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      .md
                    </a>
                  </li>
                );
              })}
            </ul>
            {pl.files.length === 0 && (
              <p className="text-sm text-foreground/50">Aucun fichier.</p>
            )}
          </section>
        );
        })}
        {playlists.length === 0 && !err && (
          <p className="text-foreground/50 text-sm">
            Aucune playlist sur le disque. Lancez des jobs depuis la page
            d’accueil.
          </p>
        )}
      </div>
    </div>
  );
}
