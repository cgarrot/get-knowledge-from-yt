import { redirect } from "next/navigation";

function firstParam(
  v: string | string[] | undefined,
): string | undefined {
  if (v === undefined) return undefined;
  return Array.isArray(v) ? v[0] : v;
}

export default async function ContentPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const rel = firstParam(sp.rel);

  if (!rel) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Contenu</h1>
        <p className="text-foreground/70">
          Paramètre <code className="font-mono text-sm">rel</code> manquant.
        </p>
      </div>
    );
  }

  redirect(`/library?rel=${encodeURIComponent(rel)}`);
}
