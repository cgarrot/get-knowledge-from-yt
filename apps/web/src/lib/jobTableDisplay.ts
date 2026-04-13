import type { Job } from "@/types/job";

/** Troncature affichée dans les colonnes « Activité » (tooltip = texte complet). */
export const JOB_ACTIVITY_TRUNC = 72;

/** Cellule « URL » : vraies URLs de référence pour les jobs prompt_generate. */
export function recentJobUrlSummary(j: Job): string {
  if (j.job_kind !== "prompt_generate") return j.url;
  const refs = j.payload?.video_urls;
  if (Array.isArray(refs) && refs.length > 0) {
    const first = String(refs[0] ?? "").trim();
    if (!first) {
      return (j.payload?.video_type ?? "prompt LLM").slice(0, 120);
    }
    if (refs.length === 1) return first;
    return `${first} +${refs.length - 1}`;
  }
  return (j.payload?.video_type ?? "prompt LLM").slice(0, 120);
}
