import type { Job } from "@/types/job";

/** Insert or replace by id, sort by created_at desc, cap length (dashboard live merge). */
export function upsertRecentJobs(recent: Job[], job: Job, max: number): Job[] {
  const next = [job, ...recent.filter((j) => j.id !== job.id)];
  next.sort((a, b) => b.created_at.localeCompare(a.created_at));
  return next.slice(0, max);
}
