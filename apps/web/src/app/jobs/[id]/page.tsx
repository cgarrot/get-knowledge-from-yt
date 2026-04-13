import Link from "next/link";
import { getServerApiBase } from "@/lib/api";
import type { Job } from "@/types/job";
import { JobPageClient } from "./job-page-client";

async function fetchJob(id: string): Promise<Job | null> {
  const base = getServerApiBase();
  const res = await fetch(`${base}/jobs/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const job = await fetchJob(id);
  if (!job) {
    return (
      <div className="space-y-4">
        <p>Job introuvable.</p>
        <Link href="/" className="text-sky-600 dark:text-sky-400 underline">
          Retour
        </Link>
      </div>
    );
  }

  return <JobPageClient initialJob={job} />;
}
