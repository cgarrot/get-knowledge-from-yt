"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import {
  MODEL_OPTIONS_FALLBACK,
  type ModelsOptionsResponse,
} from "@/lib/modelOptions";
import {
  resolveLlmFormFromStorage,
  writeLlmFormPrefs,
} from "@/lib/llmFormPrefs";
import type { Job } from "@/types/job";
import { StatusBadge } from "@/components/StatusBadge";

interface StreamPayload {
  counts: Record<string, number>;
  recent: Job[];
}

interface PromptOption {
  name: string;
  source: string;
}

interface OpencodeAccountRow {
  index: number;
  email: string | null;
  last_used: number;
  enabled: boolean;
  has_refresh_token: boolean;
  active_for_gemini: boolean;
}

const HOME_LLM_DEFAULTS = {
  provider: "gemini" as const,
  model: MODEL_OPTIONS_FALLBACK.gemini.default,
  thinking_level: "minimal",
};

export function HomeDashboard() {
  const [urls, setUrls] = useState("");
  const [playlistLabel, setPlaylistLabel] = useState("default");
  const [modelOptions, setModelOptions] = useState<ModelsOptionsResponse | null>(
    null,
  );
  const [model, setModel] = useState(HOME_LLM_DEFAULTS.model);
  const [thinkingLevel, setThinkingLevel] = useState(
    HOME_LLM_DEFAULTS.thinking_level,
  );
  const [provider, setProvider] = useState<"gemini" | "antigravity">(
    HOME_LLM_DEFAULTS.provider,
  );
  const reconciledModelOptions = useRef(false);
  const skipInitialLlmPersist = useRef(true);
  const [collectionMode, setCollectionMode] = useState<"manual" | "auto">(
    "manual",
  );
  const [classifierProvider, setClassifierProvider] = useState<
    "gemini" | "antigravity"
  >("gemini");
  const [classifierModel, setClassifierModel] = useState(
    MODEL_OPTIONS_FALLBACK.gemini.default,
  );
  const [prompt, setPrompt] = useState("default");
  const [promptOptions, setPromptOptions] = useState<PromptOption[]>([]);
  const [force, setForce] = useState(false);
  const [autoTitle, setAutoTitle] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<StreamPayload | null>(null);
  const [agConnected, setAgConnected] = useState<boolean | null>(null);
  const [agEmail, setAgEmail] = useState<string | null>(null);
  const [opencodeAccounts, setOpencodeAccounts] = useState<OpencodeAccountRow[]>(
    [],
  );
  const [opencodePick, setOpencodePick] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/jobs?limit=40`);
      if (!res.ok) return;
      const data = await res.json();
      const jobs = data.jobs as Job[];
      const counts: Record<string, number> = {};
      for (const j of jobs) {
        counts[j.status] = (counts[j.status] ?? 0) + 1;
      }
      setLive({ counts, recent: jobs });
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  const loadPrompts = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/prompts`);
      if (!res.ok) return;
      const data = await res.json();
      setPromptOptions((data.prompts as PromptOption[]) ?? []);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadPrompts();
  }, [loadPrompts]);

  useEffect(() => {
    const r = resolveLlmFormFromStorage(
      MODEL_OPTIONS_FALLBACK,
      HOME_LLM_DEFAULTS,
    );
    setProvider(r.provider);
    setModel(r.model);
    setThinkingLevel(r.thinking_level);
  }, []);

  useEffect(() => {
    if (!promptOptions.length) return;
    if (!promptOptions.some((p) => p.name === prompt)) {
      const fallback =
        promptOptions.find((p) => p.name === "default") ?? promptOptions[0];
      setPrompt(fallback.name);
    }
  }, [promptOptions, prompt]);

  useEffect(() => {
    const base = getApiBase();
    fetch(`${base}/options/models`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ModelsOptionsResponse | null) => {
        if (data?.gemini?.models?.length && data?.antigravity?.models?.length) {
          setModelOptions(data);
        }
      })
      .catch(() => {});
  }, []);

  const opts = modelOptions ?? MODEL_OPTIONS_FALLBACK;

  useEffect(() => {
    if (!modelOptions || reconciledModelOptions.current) return;
    reconciledModelOptions.current = true;
    const r = resolveLlmFormFromStorage(modelOptions, HOME_LLM_DEFAULTS);
    setProvider(r.provider);
    setModel(r.model);
    setThinkingLevel(r.thinking_level);
  }, [modelOptions]);

  useEffect(() => {
    if (skipInitialLlmPersist.current) {
      skipInitialLlmPersist.current = false;
      return;
    }
    writeLlmFormPrefs({
      provider,
      model,
      thinking_level: thinkingLevel,
    });
  }, [provider, model, thinkingLevel]);

  useEffect(() => {
    const { models, default: def } = opts[provider];
    if (!models.includes(model)) setModel(def);
  }, [provider, opts, model]);

  useEffect(() => {
    const { models, default: def } = opts[classifierProvider];
    if (!models.includes(classifierModel)) setClassifierModel(def);
  }, [classifierProvider, opts, classifierModel]);

  useEffect(() => {
    const base = getApiBase();
    fetch(`${base}/settings/collection-classifier`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: Record<string, unknown> | null) => {
        if (!data) return;
        const p = data.default_provider;
        const m = data.default_model;
        if (p === "gemini" || p === "antigravity") {
          setClassifierProvider(p);
        }
        if (typeof m === "string" && m) {
          setClassifierModel(m);
        }
      })
      .catch(() => {});
  }, []);

  const applyAntigravityStatus = useCallback(
    (data: { connected?: boolean; email?: string | null }) => {
      const ok = Boolean(data.connected);
      setAgConnected(ok);
      setAgEmail(
        ok && typeof data.email === "string" && data.email.trim()
          ? data.email.trim()
          : null,
      );
    },
    [],
  );

  const checkAntigravityAuth = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/auth/antigravity/status`);
      if (!res.ok) {
        setAgConnected(null);
        setAgEmail(null);
        return;
      }
      applyAntigravityStatus(await res.json());
    } catch {
      setAgConnected(null);
      setAgEmail(null);
    }
  }, [applyAntigravityStatus]);

  const disconnectAntigravity = useCallback(async () => {
    setError(null);
    setMessage(null);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/auth/antigravity/logout`, {
        method: "POST",
      });
      if (!res.ok) {
        const t = await res.text();
        setError(t || "Déconnexion Antigravity impossible.");
        return;
      }
      const data = (await res.json()) as {
        ok?: boolean;
        connected?: boolean;
        email?: string | null;
      };
      applyAntigravityStatus(data);
      if (data.connected) {
        setMessage(
          "Jeton enregistré par l’app supprimé, mais un autre refresh token est encore actif (variable d’environnement, fichier OpenCode, etc.).",
        );
      } else {
        setMessage(
          "Antigravity : déconnecté. Tu peux te reconnecter avec le bon compte.",
        );
      }
    } catch {
      setError("Déconnexion Antigravity : erreur réseau.");
    }
  }, [applyAntigravityStatus]);

  const importAntigravityFromOpenCode = useCallback(
    async (accountIndex: number | null) => {
      setError(null);
      setMessage(null);
      try {
        const base = getApiBase();
        const q =
          accountIndex !== null && Number.isInteger(accountIndex)
            ? `?account_index=${encodeURIComponent(String(accountIndex))}`
            : "";
        const res = await fetch(
          `${base}/auth/antigravity/import-opencode${q}`,
          {
            method: "POST",
          },
        );
        if (!res.ok) {
          const t = await res.text();
          setError(t || "Import OpenCode impossible.");
          return;
        }
        const data = (await res.json()) as {
          ok?: boolean;
          connected?: boolean;
          email?: string | null;
        };
        applyAntigravityStatus(data);
        if (data.connected) {
          setMessage(
            "Token OpenCode copié vers data/ — pense à « Rafraîchir le statut » si l’e-mail ne suit pas.",
          );
        } else {
          setMessage(
            "Import terminé mais le statut reste déconnecté — rafraîchis ou vérifie les logs API.",
          );
        }
      } catch {
        setError("Import OpenCode : erreur réseau.");
      }
    },
    [applyAntigravityStatus],
  );

  useEffect(() => {
    if (provider !== "antigravity") {
      setAgConnected(null);
      setAgEmail(null);
      setOpencodeAccounts([]);
      return;
    }
    checkAntigravityAuth();
  }, [provider, checkAntigravityAuth]);

  useEffect(() => {
    if (provider !== "antigravity") return;
    const base = getApiBase();
    fetch(`${base}/auth/antigravity/opencode-accounts`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { accounts?: OpencodeAccountRow[] } | null) => {
        setOpencodeAccounts(
          Array.isArray(d?.accounts) ? d.accounts : [],
        );
      })
      .catch(() => setOpencodeAccounts([]));
  }, [provider]);

  useEffect(() => {
    const usable = opencodeAccounts.filter((a) => a.has_refresh_token);
    if (!usable.length) return;
    setOpencodePick((prev) => {
      if (usable.some((a) => a.index === prev)) return prev;
      const active = usable.find((a) => a.active_for_gemini);
      return active?.index ?? usable[0]!.index;
    });
  }, [opencodeAccounts]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("antigravity_connected") === "1") {
      setMessage("Antigravity : connexion enregistrée.");
      checkAntigravityAuth();
      window.history.replaceState({}, "", window.location.pathname);
    }
    const agErr = params.get("antigravity_error");
    if (agErr) {
      const agErrText =
        agErr === "oauth_not_configured"
          ? "configuration OAuth manquante côté API (variables ANTIGRAVITY_OAUTH_* et ANTIGRAVITY_PROJECT_ID — voir README)."
          : decodeURIComponent(agErr);
      setError(`Antigravity OAuth : ${agErrText}`);
      checkAntigravityAuth();
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [checkAntigravityAuth]);

  useEffect(() => {
    const base = getApiBase();
    const es = new EventSource(`${base}/jobs/stream`);
    es.onmessage = (ev) => {
      try {
        const p = JSON.parse(ev.data) as StreamPayload;
        setLive(p);
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSubmitting(true);
    try {
      const base = getApiBase();
      const payload: Record<string, unknown> = {
        urls,
        playlist_label: playlistLabel,
        playlist_auto: collectionMode === "auto",
        model,
        thinking_level: thinkingLevel,
        provider,
        force,
        prompt,
        auto_title: autoTitle,
      };
      if (collectionMode === "auto") {
        if (classifierProvider !== provider) {
          payload.classifier_provider = classifierProvider;
        }
        if (classifierModel !== model) {
          payload.classifier_model = classifierModel;
        }
      }
      const res = await fetch(`${base}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const data = await res.json();
      setMessage(
        `${data.job_ids?.length ?? 0} job(s) en file — ${data.urls?.length ?? 0} URL(s) valides`,
      );
      setUrls("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const pending =
    (live?.counts?.pending ?? 0) + (live?.counts?.processing ?? 0);

  return (
    <div className="space-y-10">
      <section className="rounded-xl border border-black/10 dark:border-white/10 p-6 space-y-4">
        <h2 className="text-lg font-medium">Nouvelles URLs</h2>
        <p className="text-sm text-foreground/70">
          Une URL par ligne. Les lignes vides et les commentaires (#) sont
          ignorés. Même logique de normalisation que le CLI.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <textarea
            className="w-full min-h-[140px] rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
            placeholder="https://www.youtube.com/watch?v=..."
            value={urls}
            onChange={(e) => setUrls(e.target.value)}
            required
          />
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2 space-y-2">
              <span className="text-sm text-foreground/70">Collection</span>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="collectionMode"
                    checked={collectionMode === "manual"}
                    onChange={() => setCollectionMode("manual")}
                  />
                  Manuel (dossier fixe)
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="collectionMode"
                    checked={collectionMode === "auto"}
                    onChange={() => setCollectionMode("auto")}
                  />
                  Automatique (LLM choisit dossier / sous-dossier)
                </label>
              </div>
              {collectionMode === "manual" ? (
                <label className="text-sm space-y-1 block">
                  <span className="text-foreground/70">Dossier (tu peux utiliser parent/sous-dossier)</span>
                  <input
                    className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
                    value={playlistLabel}
                    onChange={(e) => setPlaylistLabel(e.target.value)}
                  />
                </label>
              ) : (
                <div className="space-y-3 rounded-lg border border-black/10 dark:border-white/10 p-3">
                  <label className="text-sm space-y-1 block">
                    <span className="text-foreground/70">
                      Dossier de secours (si classification impossible)
                    </span>
                    <input
                      className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
                      value={playlistLabel}
                      onChange={(e) => setPlaylistLabel(e.target.value)}
                    />
                  </label>
                  <p className="text-xs text-foreground/50">
                    Consignes globales et thinking : page{" "}
                    <Link
                      href="/settings/collections"
                      className="text-sky-600 dark:text-sky-400 underline"
                    >
                      Classement LLM
                    </Link>
                    . Ci-dessous : surcharger provider / modèle pour la classification
                    uniquement (par défaut = même que l’ingest ci-dessous).
                  </p>
                  <label className="text-sm space-y-1 block">
                    <span className="text-foreground/70">Provider (classification)</span>
                    <select
                      className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
                      value={classifierProvider}
                      onChange={(e) =>
                        setClassifierProvider(
                          e.target.value as "gemini" | "antigravity",
                        )
                      }
                    >
                      <option value="gemini">gemini (Gemini API + clé)</option>
                      <option value="antigravity">antigravity (OAuth)</option>
                    </select>
                  </label>
                  <label className="text-sm space-y-1 block">
                    <span className="text-foreground/70">Modèle (classification)</span>
                    <select
                      className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
                      value={classifierModel}
                      onChange={(e) => setClassifierModel(e.target.value)}
                    >
                      {opts[classifierProvider].models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                          {m === opts[classifierProvider].default ? " (défaut)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
            </div>
            <label className="text-sm space-y-1">
              <span className="text-foreground/70">Prompt</span>
              <select
                className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onFocus={() => loadPrompts()}
                disabled={promptOptions.length === 0}
              >
                {promptOptions.length === 0 ? (
                  <option value="default">Chargement…</option>
                ) : (
                  promptOptions.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name} ({p.source})
                    </option>
                  ))
                )}
              </select>
              <span className="text-xs text-foreground/50 block mt-1">
                Liste synchronisée SQLite + fichiers — rafraîchit au focus.
              </span>
            </label>
            <label className="text-sm space-y-1">
              <span className="text-foreground/70">Provider</span>
              <select
                className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
                value={provider}
                onChange={(e) =>
                  setProvider(e.target.value as "gemini" | "antigravity")
                }
              >
                <option value="gemini">gemini (Gemini API + clé)</option>
                <option value="antigravity">antigravity (OAuth)</option>
              </select>
            </label>
            {provider === "antigravity" ? (
              <div className="sm:col-span-2 rounded-lg border border-amber-500/30 bg-amber-500/5 dark:bg-amber-500/10 px-4 py-3 flex flex-wrap items-center gap-3">
                {agConnected === null ? (
                  <span className="text-sm text-foreground/60">
                    Vérification de la session Antigravity…
                  </span>
                ) : agConnected ? (
                  <>
                    <span className="text-sm text-emerald-700 dark:text-emerald-300">
                      Antigravity : connecté
                      {agEmail ? (
                        <>
                          {" "}
                          — <span className="font-medium">{agEmail}</span>
                        </>
                      ) : (
                        " (refresh token présent)."
                      )}
                    </span>
                    <button
                      type="button"
                      className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm shrink-0"
                      onClick={() => checkAntigravityAuth()}
                    >
                      Rafraîchir le statut
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-red-500/35 text-red-800 dark:text-red-300 px-3 py-2 text-sm shrink-0"
                      onClick={() => void disconnectAntigravity()}
                    >
                      Déconnexion
                    </button>
                  </>
                ) : (
                  <>
                    <span className="text-sm text-foreground/80">
                      Aucun refresh token pour ce serveur. OAuth web, ou import du compte
                      déjà connecté dans OpenCode (
                      <code className="text-xs">~/.config/opencode/antigravity-accounts.json</code>
                      , même machine que l’API).
                    </span>
                    <button
                      type="button"
                      className="rounded-lg bg-foreground text-background px-3 py-2 text-sm font-medium shrink-0"
                      onClick={() => {
                        window.location.href = `${getApiBase()}/auth/antigravity/login`;
                      }}
                    >
                      Se connecter (Antigravity)
                    </button>
                    {opencodeAccounts.filter((a) => a.has_refresh_token).length >
                    0 ? (
                      <label className="flex items-center gap-2 text-sm">
                        <span className="text-foreground/70 shrink-0">
                          Compte OpenCode
                        </span>
                        <select
                          className="rounded-lg border border-black/15 dark:border-white/15 bg-background px-2 py-2 text-sm max-w-[220px]"
                          value={opencodePick}
                          onChange={(e) =>
                            setOpencodePick(Number.parseInt(e.target.value, 10))
                          }
                        >
                          {opencodeAccounts
                            .filter((a) => a.has_refresh_token)
                            .map((a) => (
                              <option key={a.index} value={a.index}>
                                #{a.index}
                                {a.email ? ` ${a.email}` : ""}
                                {a.active_for_gemini ? " (actif Antigravity)" : ""}
                              </option>
                            ))}
                        </select>
                        <button
                          type="button"
                          className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm shrink-0"
                          onClick={() =>
                            void importAntigravityFromOpenCode(opencodePick)
                          }
                        >
                          Importer ce compte
                        </button>
                      </label>
                    ) : (
                      <button
                        type="button"
                        className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm shrink-0"
                        onClick={() => void importAntigravityFromOpenCode(null)}
                      >
                        Importer OpenCode (auto)
                      </button>
                    )}
                    <button
                      type="button"
                      className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm shrink-0"
                      onClick={() => checkAntigravityAuth()}
                    >
                      Rafraîchir le statut
                    </button>
                  </>
                )}
              </div>
            ) : null}
            <label className="text-sm space-y-1">
              <span className="text-foreground/70">
                Modèle ({provider})
                {provider === "gemini" ? (
                  <a
                    href="https://ai.google.dev/gemini-api/docs/models"
                    target="_blank"
                    rel="noreferrer"
                    className="ml-2 text-sky-600 dark:text-sky-400 font-normal"
                  >
                    doc Google
                  </a>
                ) : null}
              </span>
              <select
                className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {opts[provider].models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                    {m === opts[provider].default ? " (défaut)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm space-y-1">
              <span className="text-foreground/70">Thinking level</span>
              <select
                className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
                value={thinkingLevel}
                onChange={(e) => setThinkingLevel(e.target.value)}
              >
                {(["minimal", "low", "medium", "high"] as const).map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex flex-wrap gap-6 text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
              />
              Forcer la régénération
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoTitle}
                onChange={(e) => setAutoTitle(e.target.checked)}
              />
              Titres YouTube (oEmbed) pour les noms de fichiers
            </label>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-foreground text-background px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {submitting ? "Envoi…" : "Mettre en file"}
          </button>
          {message && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              {message}
            </p>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </form>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">File & activité récente</h2>
          {live?.counts && (
            <p className="text-sm text-foreground/70 font-mono">
              En cours: {pending} —{" "}
              {Object.entries(live.counts)
                .map(([k, v]) => `${k}:${v}`)
                .join(" ")}
            </p>
          )}
        </div>
        <div className="rounded-xl border border-black/10 dark:border-white/10 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/10 dark:border-white/10 text-left text-foreground/60">
                <th className="p-3 font-medium">Statut</th>
                <th className="p-3 font-medium">URL</th>
                <th className="p-3 font-medium">Collection</th>
                <th className="p-3 font-medium">Prompt</th>
                <th className="p-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {(live?.recent ?? []).map((j) => (
                <tr
                  key={j.id}
                  className="border-b border-black/5 dark:border-white/5"
                >
                  <td className="p-3">
                    <StatusBadge status={j.status} />
                  </td>
                  <td className="p-3 max-w-[200px] truncate font-mono text-xs">
                    {j.url}
                  </td>
                  <td className="p-3">
                    {j.playlist_label}
                    {j.playlist_auto ? (
                      <span className="ml-1 text-xs text-foreground/50">(auto)</span>
                    ) : null}
                  </td>
                  <td className="p-3">{j.prompt_name}</td>
                  <td className="p-3">
                    <Link
                      href={`/jobs/${j.id}`}
                      className="text-sky-600 dark:text-sky-400 hover:underline"
                    >
                      Détail
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!live?.recent?.length && (
            <p className="p-6 text-foreground/50 text-sm">Aucun job pour le moment.</p>
          )}
        </div>
      </section>
    </div>
  );
}
