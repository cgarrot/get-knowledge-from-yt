export type JobStatus =
  | "pending"
  | "processing"
  | "cancelled"
  | "ok"
  | "error"
  | "skipped";

export type JobKind = "video" | "prompt_generate";

export interface PromptGenerateJobPayload {
  video_type?: string;
  extra_notes?: string;
  video_urls?: string[];
  save_to_name?: string | null;
}

export interface Job {
  id: string;
  url: string;
  playlist_label: string;
  status: JobStatus;
  model: string;
  thinking_level: string;
  provider: string;
  force: boolean;
  prompt_name: string;
  auto_title: boolean;
  playlist_auto: boolean;
  classifier_provider: string | null;
  classifier_model: string | null;
  analysis_markdown?: string | null;
  output_rel_path: string | null;
  error_message: string | null;
  log_message: string | null;
  job_kind?: JobKind;
  payload?: PromptGenerateJobPayload | null;
  created_at: string;
  updated_at: string;
}
