function normalizeApiBase(raw: string): string {
  return raw.replace(/\/$/, "");
}

/** Base API URL for the browser (SSH tunnel / host loopback). */
export function getApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  return normalizeApiBase(raw);
}

/**
 * Base URL for server-side fetch (Server Components, route handlers).
 * Under Docker Compose, set INTERNAL_API_URL=http://api:8000 so SSR reaches the api service;
 * NEXT_PUBLIC_API_URL often stays http://127.0.0.1:8000 for the browser.
 */
export function getServerApiBase(): string {
  const raw =
    process.env.INTERNAL_API_URL ??
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://127.0.0.1:8000";
  return normalizeApiBase(raw);
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${getServerApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}
