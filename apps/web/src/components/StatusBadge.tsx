import type { JobStatus } from "@/types/job";

const styles: Record<JobStatus, string> = {
  pending: "bg-amber-500/20 text-amber-800 dark:text-amber-200",
  processing: "bg-sky-500/20 text-sky-800 dark:text-sky-200",
  ok: "bg-emerald-500/20 text-emerald-800 dark:text-emerald-200",
  error: "bg-red-500/20 text-red-800 dark:text-red-200",
  skipped: "bg-zinc-500/20 text-zinc-700 dark:text-zinc-300",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${styles[status]}`}
    >
      {status}
    </span>
  );
}
