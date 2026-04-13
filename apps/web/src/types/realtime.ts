import type { Job } from "@/types/job";

export interface JobsSnapshotData {
  counts: Record<string, number>;
  recent: Job[];
}

export type GkfyRealtimeMessage =
  | { type: "snapshot"; data: JobsSnapshotData }
  | { type: "job_created"; data: { job: Job } }
  | { type: "job_updated"; data: { job: Job } }
  | { type: "job_cancelled"; data: { job: Job } }
  | { type: "artifact_updated"; data: { rel: string } }
  | { type: "prompt_saved"; data: { name: string; source: string } }
  | { type: "prompt_deleted"; data: { name: string } }
  | { type: "heartbeat"; data: Record<string, never> };
