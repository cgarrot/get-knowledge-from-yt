"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import {
  MODEL_OPTIONS_FALLBACK,
  type ModelsOptionsResponse,
} from "@/lib/modelOptions";
import {
  resolveLlmFormFromStorage,
  writeLlmFormPrefs,
} from "@/lib/llmFormPrefs";

interface PromptInfo {
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

const VIDEO_TYPE_SUGGESTIONS = [
  "Tutoriel technique / code",
  "Conférence / keynote",
  "Podcast / interview",
  "Review produit",
  "Documentaire / vulgarisation",
];

const THINKING_LEVELS = ["minimal", "low", "medium", "high"] as const;

const PROMPTS_GEN_LLM_DEFAULTS = {
  provider: "gemini" as const,
  model: MODEL_OPTIONS_FALLBACK.gemini.default,
  thinking_level: "medium",
};

function slugifyPromptBase(videoType: string): string {
  const raw = videoType
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  const core = raw || "prompt-gen";
  return `auto-${core}`;
}

function uniquePromptName(base: string, existing: Set<string>): string {
  if (!existing.has(base)) return base;
  let n = 2;
  while (existing.has(`${base}-${n}`)) n += 1;
  return `${base}-${n}`;
}

export default function PromptsPage() {
  const [list, setList] = useState<PromptInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [source, setSource] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [modelOptions, setModelOptions] = useState<ModelsOptionsResponse | null>(
    null,
  );
  // Initial render must match SSR: never read localStorage in useState init.
  const [genProvider, setGenProvider] = useState<"gemini" | "antigravity">(
    PROMPTS_GEN_LLM_DEFAULTS.provider,
  );
  const [genModel, setGenModel] = useState(PROMPTS_GEN_LLM_DEFAULTS.model);
  const [genThinking, setGenThinking] = useState<string>(
    PROMPTS_GEN_LLM_DEFAULTS.thinking_level,
  );
  const skipInitialLlmPersist = useRef(true);
  const reconciledModelOptions = useRef(false);
  const [videoType, setVideoType] = useState("");
  const [referenceVideoUrls, setReferenceVideoUrls] = useState("");
  const [extraNotes, setExtraNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [agConnected, setAgConnected] = useState<boolean | null>(null);
  const [agEmail, setAgEmail] = useState<string | null>(null);
  const [opencodeAccounts, setOpencodeAccounts] = useState<OpencodeAccountRow[]>(
    [],
  );
  const [opencodePick, setOpencodePick] = useState(0);

  const opts = modelOptions ?? MODEL_OPTIONS_FALLBACK;

  const loadList = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/prompts`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setList(data.prompts ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    const r = resolveLlmFormFromStorage(
      MODEL_OPTIONS_FALLBACK,
      PROMPTS_GEN_LLM_DEFAULTS,
    );
    setGenProvider(r.provider);
    setGenModel(r.model);
    setGenThinking(r.thinking_level);
  }, []);

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

  useEffect(() => {
    const { models, default: def } = opts[genProvider];
    if (!models.includes(genModel)) setGenModel(def);
  }, [genProvider, opts, genModel]);

  useEffect(() => {
    if (!modelOptions || reconciledModelOptions.current) return;
    reconciledModelOptions.current = true;
    const r = resolveLlmFormFromStorage(modelOptions, PROMPTS_GEN_LLM_DEFAULTS);
    setGenProvider(r.provider);
    setGenModel(r.model);
    setGenThinking(r.thinking_level);
  }, [modelOptions]);

  useEffect(() => {
    if (skipInitialLlmPersist.current) {
      skipInitialLlmPersist.current = false;
      return;
    }
    writeLlmFormPrefs({
      provider: genProvider,
      model: genModel,
      thinking_level: genThinking,
    });
  }, [genProvider, genModel, genThinking]);

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
            "Token OpenCode copié vers data/ — rafraîchis le statut si besoin.",
          );
        } else {
          setMessage("Import terminé — statut encore déconnecté, vérifie l’API.");
        }
      } catch {
        setError("Import OpenCode : erreur réseau.");
      }
    },
    [applyAntigravityStatus],
  );

  useEffect(() => {
    if (genProvider !== "antigravity") {
      setAgConnected(null);
      setAgEmail(null);
      setOpencodeAccounts([]);
      return;
    }
    checkAntigravityAuth();
  }, [genProvider, checkAntigravityAuth]);

  useEffect(() => {
    if (genProvider !== "antigravity") return;
    const base = getApiBase();
    fetch(`${base}/auth/antigravity/opencode-accounts`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { accounts?: OpencodeAccountRow[] } | null) => {
        setOpencodeAccounts(Array.isArray(d?.accounts) ? d.accounts : []);
      })
      .catch(() => setOpencodeAccounts([]));
  }, [genProvider]);

  useEffect(() => {
    const usable = opencodeAccounts.filter((a) => a.has_refresh_token);
    if (!usable.length) return;
    setOpencodePick((prev) => {
      if (usable.some((a) => a.index === prev)) return prev;
      const active = usable.find((a) => a.active_for_gemini);
      return active?.index ?? usable[0]!.index;
    });
  }, [opencodeAccounts]);

  const loadOne = async (name: string) => {
    setError(null);
    setMessage(null);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/prompts/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSelected(name);
      setContent(data.content ?? "");
      setSource(data.source ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  async function save() {
    if (!selected) return;
    setError(null);
    setMessage(null);
    try {
      const base = getApiBase();
      const res = await fetch(
        `${base}/prompts/${encodeURIComponent(selected)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        },
      );
      if (!res.ok) throw new Error(await res.text());
      setMessage("Enregistré dans data/prompts (override utilisateur).");
      setSource("user");
      loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function createNew() {
    const name = newName.trim();
    if (!name || name.includes("/") || name.includes("..")) {
      setError("Nom invalide.");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const base = getApiBase();
      const res = await fetch(
        `${base}/prompts/${encodeURIComponent(name)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content:
              '<!-- user_turn: "Analyze the referenced YouTube video and output ONLY the wiki document following the required format in your instructions. Do not prepend any preamble." -->\n\n',
          }),
        },
      );
      if (!res.ok) throw new Error(await res.text());
      setNewName("");
      setMessage(`Prompt « ${name} » créé.`);
      await loadList();
      await loadOne(name);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function removeUser() {
    if (!selected || source !== "user") return;
    if (!confirm(`Supprimer le prompt utilisateur « ${selected} » ?`)) return;
    setError(null);
    setMessage(null);
    try {
      const base = getApiBase();
      const res = await fetch(
        `${base}/prompts/${encodeURIComponent(selected)}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error(await res.text());
      setMessage("Supprimé.");
      setSelected(null);
      setContent("");
      setSource(null);
      loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function generateWithLlm() {
    const vt = videoType.trim();
    if (!vt) {
      setError("Indiquez un type de vidéo.");
      return;
    }
    if (
      selected &&
      content.trim() &&
      !confirm("Remplacer le contenu actuel par le prompt généré ?")
    ) {
      return;
    }
    setError(null);
    setMessage(null);
    setGenerating(true);
    try {
      const base = getApiBase();
      const video_urls = referenceVideoUrls
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await fetch(`${base}/prompts/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: genProvider,
          model: genModel,
          video_type: vt,
          thinking_level: genThinking,
          extra_notes: extraNotes.trim(),
          video_urls,
        }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const data = await res.json();
      const text = (data.content as string) ?? "";

      if (!selected) {
        const catalogRes = await fetch(`${base}/prompts`);
        if (!catalogRes.ok) throw new Error(await catalogRes.text());
        const catalogData = await catalogRes.json();
        const fresh = (catalogData.prompts as PromptInfo[]) ?? [];
        const used = new Set(fresh.map((p) => p.name));
        const newName = uniquePromptName(slugifyPromptBase(vt), used);
        const putRes = await fetch(
          `${base}/prompts/${encodeURIComponent(newName)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: text }),
          },
        );
        if (!putRes.ok) throw new Error(await putRes.text());
        setSelected(newName);
        setContent(text);
        setSource("user");
        await loadList();
        setMessage(
          `Prompt généré et enregistré sous « ${newName} » (data/prompts).`,
        );
      } else {
        setContent(text);
        setMessage(
          "Prompt généré dans l’éditeur — enregistrez pour appliquer au fichier.",
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Prompts</h1>
        <p className="text-sm text-foreground/70 mt-1 max-w-2xl">
          Les prompts intégrés au package sont en lecture seule ; une copie
          utilisateur dans <code className="font-mono text-xs">data/prompts</code>{" "}
          remplace le même nom. Format : optionnellement une première ligne{" "}
          <code className="font-mono text-xs">
            &lt;!-- user_turn: &quot;...&quot; --&gt;
          </code>{" "}
          puis l’instruction système.
        </p>
      </div>

      <section className="rounded-xl border border-black/10 dark:border-white/10 p-4 space-y-4 max-w-4xl">
        <h2 className="text-sm font-semibold tracking-tight">
          Génération automatique (LLM)
        </h2>
        <p className="text-xs text-foreground/60">
          Décrivez le type de vidéo cible ; optionnellement ajoutez des URLs
          YouTube (une par ligne) pour que le LLM s’appuie sur le contenu réel
          et calibre un prompt plus pertinent. Avec Gemini API, chaque URL est
          envoyée en multimodal ; avec Antigravity, seule la première l’est, les
          autres servent de contexte texte (max. 8 URLs).
        </p>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-sm space-y-1">
            <span className="text-foreground/70">Provider</span>
            <select
              className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
              value={genProvider}
              onChange={(e) =>
                setGenProvider(e.target.value as "gemini" | "antigravity")
              }
            >
              <option value="gemini">gemini (Gemini API + clé)</option>
              <option value="antigravity">antigravity (OAuth)</option>
            </select>
          </label>
          <label className="text-sm space-y-1">
            <span className="text-foreground/70">Modèle</span>
            <select
              className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
              value={genModel}
              onChange={(e) => setGenModel(e.target.value)}
            >
              {opts[genProvider].models.map((m) => (
                <option key={m} value={m}>
                  {m}
                  {m === opts[genProvider].default ? " (défaut)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm space-y-1 sm:col-span-2">
            <span className="text-foreground/70">Niveau de réflexion (génération)</span>
            <select
              className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
              value={genThinking}
              onChange={(e) => setGenThinking(e.target.value)}
            >
              {THINKING_LEVELS.map((lvl) => (
                <option key={lvl} value={lvl}>
                  {lvl}
                </option>
              ))}
            </select>
          </label>
        </div>
        {genProvider === "antigravity" ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 dark:bg-amber-500/10 px-4 py-3 flex flex-wrap items-center gap-3">
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
                    "."
                  )}
                </span>
                <button
                  type="button"
                  className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm shrink-0"
                  onClick={() => checkAntigravityAuth()}
                >
                  Rafraîchir
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
              <div className="flex flex-col gap-3">
                <span className="text-sm text-foreground/80">
                  Aucun refresh token. OAuth ou import depuis OpenCode (même machine
                  que l’API).
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="rounded-lg bg-foreground text-background px-3 py-1.5 text-xs font-medium"
                    onClick={() => {
                      window.location.href = `${getApiBase()}/auth/antigravity/login`;
                    }}
                  >
                    Se connecter (Antigravity)
                  </button>
                  {opencodeAccounts.filter((a) => a.has_refresh_token).length >
                  0 ? (
                    <>
                      <select
                        className="rounded-lg border border-black/15 dark:border-white/15 bg-background px-2 py-1.5 text-xs max-w-[200px]"
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
                              {a.active_for_gemini ? " (actif)" : ""}
                            </option>
                          ))}
                      </select>
                      <button
                        type="button"
                        className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-1.5 text-xs"
                        onClick={() =>
                          void importAntigravityFromOpenCode(opencodePick)
                        }
                      >
                        Importer ce compte
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-1.5 text-xs"
                      onClick={() => void importAntigravityFromOpenCode(null)}
                    >
                      Importer OpenCode (auto)
                    </button>
                  )}
                  <button
                    type="button"
                    className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-1.5 text-xs"
                    onClick={() => checkAntigravityAuth()}
                  >
                    Rafraîchir
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : null}
        <label className="text-sm space-y-1 block">
          <span className="text-foreground/70">Type de vidéo</span>
          <input
            className="w-full rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
            value={videoType}
            onChange={(e) => setVideoType(e.target.value)}
            placeholder="ex. tutoriel Rust async, keynote produit SaaS…"
          />
        </label>
        <label className="text-sm space-y-1 block">
          <span className="text-foreground/70">
            URLs de vidéos de référence (optionnel)
          </span>
          <textarea
            className="w-full min-h-[88px] rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
            value={referenceVideoUrls}
            onChange={(e) => setReferenceVideoUrls(e.target.value)}
            placeholder={
              "https://www.youtube.com/watch?v=…\nhttps://youtu.be/…"
            }
          />
        </label>
        <div className="flex flex-wrap gap-2">
          {VIDEO_TYPE_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="rounded-full border border-black/15 dark:border-white/15 px-3 py-1 text-xs"
              onClick={() => setVideoType(s)}
            >
              {s}
            </button>
          ))}
        </div>
        <label className="text-sm space-y-1 block">
          <span className="text-foreground/70">Notes (optionnel)</span>
          <textarea
            className="w-full min-h-[72px] rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
            value={extraNotes}
            onChange={(e) => setExtraNotes(e.target.value)}
            placeholder="Public, langue, chaîne, contraintes de format…"
          />
        </label>
        <button
          type="button"
          onClick={generateWithLlm}
          disabled={generating}
          className="rounded-lg bg-foreground text-background px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {generating ? "Génération…" : "Générer le prompt"}
        </button>
        <p className="text-xs text-foreground/50">
          Sans prompt sélectionné : un nom du type{" "}
          <code className="font-mono text-[11px]">auto-…</code> est créé à partir
          du type de vidéo, le fichier est enregistré dans{" "}
          <code className="font-mono text-[11px]">data/prompts</code>. Avec un
          prompt ouvert : le texte est inséré dans l’éditeur (enregistrement
          manuel).
        </p>
      </section>

      <div className="flex flex-wrap gap-2 items-end">
        <input
          className="rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
          placeholder="nouveau-nom"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button
          type="button"
          onClick={createNew}
          className="rounded-lg border border-black/15 dark:border-white/15 px-3 py-2 text-sm"
        >
          Créer
        </button>
      </div>

      <div className="grid lg:grid-cols-[220px_1fr] gap-6">
        <aside className="rounded-xl border border-black/10 dark:border-white/10 p-3 max-h-[70vh] overflow-y-auto">
          <ul className="text-sm space-y-1">
            {list.map((p) => (
              <li key={p.name}>
                <button
                  type="button"
                  onClick={() => loadOne(p.name)}
                  className={`w-full text-left px-2 py-1 rounded font-mono text-xs ${
                    selected === p.name
                      ? "bg-foreground/10"
                      : "hover:bg-foreground/5"
                  }`}
                >
                  {p.name}
                  <span className="text-foreground/50 ml-1">({p.source})</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="space-y-3">
          {selected && (
            <p className="text-sm text-foreground/70">
              Édition : <span className="font-mono">{selected}</span> — source{" "}
              <span className="font-mono">{source}</span>
            </p>
          )}
          <textarea
            className="w-full min-h-[420px] rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm font-mono"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Sélectionnez un prompt…"
            disabled={!selected}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={save}
              disabled={!selected}
              className="rounded-lg bg-foreground text-background px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              Enregistrer (data/prompts)
            </button>
            <button
              type="button"
              onClick={removeUser}
              disabled={!selected || source !== "user"}
              className="rounded-lg border border-red-500/50 text-red-600 dark:text-red-400 px-4 py-2 text-sm disabled:opacity-50"
            >
              Supprimer copie utilisateur
            </button>
          </div>
          {message && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              {message}
            </p>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
