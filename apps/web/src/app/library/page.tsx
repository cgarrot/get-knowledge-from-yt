import { Suspense } from "react";
import { LibraryClient } from "./library-client";

export default function LibraryPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-xl border border-black/10 dark:border-white/10 p-8 text-sm text-foreground/50">
          Chargement de la bibliothèque…
        </div>
      }
    >
      <LibraryClient />
    </Suspense>
  );
}
