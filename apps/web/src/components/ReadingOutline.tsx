"use client";

import { useEffect, useState } from "react";

export interface OutlineItem {
  id: string;
  text: string;
  level: number;
}

export function ReadingOutline({
  articleRef,
  contentVersion,
  className,
}: {
  articleRef: React.RefObject<HTMLElement | null>;
  /** Bumps when markdown body changes so headings are rescanned. */
  contentVersion: string;
  className?: string;
}) {
  const [items, setItems] = useState<OutlineItem[]>([]);

  useEffect(() => {
    const el = articleRef.current;
    if (!el) {
      setItems([]);
      return;
    }
    const headings = el.querySelectorAll("h1, h2, h3");
    setItems(
      [...headings].map((h) => ({
        id: h.id,
        text: h.textContent?.trim() ?? "",
        level: Number.parseInt(h.tagName.slice(1), 10) || 1,
      })),
    );
  }, [articleRef, contentVersion]);

  if (items.length === 0) return null;

  return (
    <nav
      aria-label="Sur cette page"
      className={className}
    >
      <p className="text-xs font-medium text-foreground/50 uppercase tracking-wide mb-2">
        Sur cette page
      </p>
      <ul className="space-y-1 text-sm">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="w-full text-left rounded-md px-1 py-0.5 hover:bg-black/5 dark:hover:bg-white/10 text-foreground/80 hover:text-foreground"
              style={{ paddingLeft: `${(item.level - 1) * 0.65 + 0.25}rem` }}
              onClick={() => {
                const target = document.getElementById(item.id);
                target?.scrollIntoView({ behavior: "smooth", block: "start" });
                try {
                  history.replaceState(null, "", `#${item.id}`);
                } catch {
                  /* ignore */
                }
              }}
            >
              {item.text}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
