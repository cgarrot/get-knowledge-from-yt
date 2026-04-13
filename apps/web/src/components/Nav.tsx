import Link from "next/link";

const links = [
  { href: "/", label: "Queue" },
  { href: "/history", label: "Historique" },
  { href: "/library", label: "Bibliothèque" },
  { href: "/settings/collections", label: "Classement LLM" },
  { href: "/prompts", label: "Prompts" },
];

export function Nav() {
  return (
    <header className="border-b border-black/10 dark:border-white/10 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center gap-4">
        <Link href="/" className="font-semibold text-lg tracking-tight">
          get-knowledge-from-yt
        </Link>
        <nav className="flex flex-wrap gap-3 text-sm">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-foreground/80 hover:text-foreground underline-offset-4 hover:underline"
            >
              {label}
            </Link>
          ))}
        </nav>
        <span className="text-xs text-foreground/50 ml-auto font-mono">
          API: {process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}
        </span>
      </div>
    </header>
  );
}
