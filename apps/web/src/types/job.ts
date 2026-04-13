export type JobStatus =
  | "pending"
  | "processing"
  | "ok"
  | "error"
  | "skipped";

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
  created_at: string;
  updated_at: string;
}
