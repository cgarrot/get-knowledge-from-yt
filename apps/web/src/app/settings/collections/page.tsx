"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import {
  MODEL_OPTIONS_FALLBACK,
  type ModelsOptionsResponse,
} from "@/lib/modelOptions";
import { writeLlmFormPrefs } from "@/lib/llmFormPrefs";

export default function CollectionClassifierSettingsPage() {
  const [modelOptions, setModelOptions] = useState<ModelsOptionsResponse | null>(
    null,
  );
  const [provider, setProvider] = useState<"gemini" | "antigravity">("gemini");
  const [model, setModel] = useState(MODEL_OPTIONS_FALLBACK.gemini.default);
  const [thinkingLevel, setThinkingLevel] = useState("minimal");
  const [instructions, setInstructions] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const opts = modelOptions ?? MODEL_OPTIONS_FALLBACK;

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
    const { models, default: def } = opts[provider];
    if (!models.includes(model)) setModel(def);
  }, [provider, opts, model]);

  const loadSettings = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/settings/collection-classifier`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const prov = data.default_provider ?? "gemini";
      setProvider(prov);
      setModel(
        data.default_model ??
          MODEL_OPTIONS_FALLBACK[prov === "antigravity" ? "antigravity" : "gemini"]
            .default,
      );
      setThinkingLevel(data.thinking_level ?? "minimal");
      setInstructions(data.instructions ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (loading) return;
    writeLlmFormPrefs({
      provider,
      model,
      thinking_level: thinkingLevel,
    });
  }, [loading, provider, model, thinkingLevel]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/settings/collection-classifier`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          default_provider: provider,
          default_model: model,
          thinking_level: thinkingLevel,
          instructions,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setProvider(data.default_provider);
      setModel(data.default_model);
      setThinkingLevel(data.thinking_level);
      setInstructions(data.instructions ?? "");
      setMessage("Réglages enregistrés.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Classement automatique (LLM)
        </h1>
        <p className="text-sm text-foreground/70 mt-1">
          Ces valeurs par défaut préremplissent la file d’attente quand tu choisis
          le mode automatique pour la collection. Le worker lit aussi les consignes
          et le niveau de thinking pour l’appel de classification (texte seul,
          sans vidéo). Le premier niveau de dossier est aligné sur le nom de la
          chaîne YouTube (oEmbed) pour garder une même série / même créateur au
          même endroit.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-foreground/50">Chargement…</p>
      ) : (
        <form onSubmit={onSave} className="space-y-4 rounded-xl border border-black/10 dark:border-white/10 p-6">
          <label className="text-sm space-y-1 block">
            <span className="text-foreground/70">Provider (classification)</span>
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
          <label className="text-sm space-y-1 block">
            <span className="text-foreground/70">Modèle</span>
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
          <label className="text-sm space-y-1 block">
            <span className="text-foreground/70">Thinking level (classification)</span>
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
          <label className="text-sm space-y-1 block">
            <span className="text-foreground/70">Consignes / taxonomie (optionnel)</span>
            <textarea
              className="w-full min-h-[120px] rounded-lg border border-black/15 dark:border-white/15 bg-background px-3 py-2 text-sm"
              placeholder="Ex. privilégier les dossiers existants liés au dev web, séparer tutoriels et conférences…"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-foreground text-background px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
          {message && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">{message}</p>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </form>
      )}
    </div>
  );
}
