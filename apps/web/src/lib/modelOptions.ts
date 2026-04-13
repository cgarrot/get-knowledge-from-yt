/** Mirrors python/yt_knowledge_ingest/model_options.py when API is unreachable. */

export type ProviderModels = {
  default: string;
  models: string[];
};

export type ModelsOptionsResponse = {
  gemini: ProviderModels;
  antigravity: ProviderModels;
};

export const MODEL_OPTIONS_FALLBACK: ModelsOptionsResponse = {
  gemini: {
    default: "gemini-2.5-flash",
    models: [
      "gemini-2.5-flash",
      "gemini-2.5-flash-lite",
      "gemini-2.5-pro",
      "gemini-3-flash-preview",
      "gemini-3.1-flash-lite-preview",
      "gemini-3.1-pro-preview",
    ],
  },
  antigravity: {
    default: "gemini-3-pro-high",
    models: [
      "gemini-3-pro-high",
      "gemini-3-pro-low",
      "gemini-3.1-pro-high",
      "gemini-3.1-pro-low",
      "gemini-3-flash",
      "claude-sonnet-4-6",
      "claude-opus-4-6-thinking",
      "gpt-oss-120b-medium",
    ],
  },
};
