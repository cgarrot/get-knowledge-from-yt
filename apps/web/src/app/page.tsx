import { HomeDashboard } from "@/components/HomeDashboard";

export default function Home() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight">File d’analyse</h1>
      <p className="text-foreground/70 text-sm max-w-2xl">
        Les jobs sont traités par le worker Python avec la même chaîne que{" "}
        <code className="font-mono text-xs">yt_knowledge_ingest</code> (
        <code className="font-mono text-xs">process_video_job</code>
        ).
      </p>
      <HomeDashboard />
    </div>
  );
}
