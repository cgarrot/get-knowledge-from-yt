import type { ModelsOptionsResponse } from "@/lib/modelOptions";

export const LLM_FORM_PREFS_KEY = "gkfy-llm-form-prefs";

export type LlmFormPrefs = {
  provider: "gemini" | "antigravity";
  model: string;
  thinking_level: string;
};

const THINKING_LEVELS = new Set(["minimal", "low", "medium", "high"]);

function readPartialFromStorage(): Partial<LlmFormPrefs> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LLM_FORM_PREFS_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") return null;
    const p = o as Record<string, unknown>;
    const out: Partial<LlmFormPrefs> = {};
    if (p.provider === "gemini" || p.provider === "antigravity") {
      out.provider = p.provider;
    }
    if (typeof p.model === "string" && p.model) out.model = p.model;
    if (
      typeof p.thinking_level === "string" &&
      THINKING_LEVELS.has(p.thinking_level)
    ) {
      out.thinking_level = p.thinking_level;
    }
    return Object.keys(out).length ? out : null;
  } catch {
    return null;
  }
}

/** Merge localStorage with defaults and validate against current model lists. */
export function resolveLlmFormFromStorage(
  opts: ModelsOptionsResponse,
  pageDefaults: LlmFormPrefs,
): LlmFormPrefs {
  const s = readPartialFromStorage();
  const provider: "gemini" | "antigravity" =
    s?.provider === "gemini" || s?.provider === "antigravity"
      ? s.provider
      : pageDefaults.provider;
  const models = opts[provider].models;
  let model: string;
  if (s?.model && models.includes(s.model)) {
    model = s.model;
  } else if (models.includes(pageDefaults.model)) {
    model = pageDefaults.model;
  } else {
    model = opts[provider].default;
  }
  const thinking_level =
    s?.thinking_level && THINKING_LEVELS.has(s.thinking_level)
      ? s.thinking_level
      : pageDefaults.thinking_level;
  return { provider, model, thinking_level };
}

export function writeLlmFormPrefs(prefs: LlmFormPrefs): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LLM_FORM_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* quota / private mode */
  }
}
