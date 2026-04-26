/**
 * A14 — API fetch wrapper with Bearer token.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("engram_token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(getApiUrl(path), {
    ...options,
    headers,
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("engram_token");
      window.location.href = "/login";
    }
    throw new Error("Not authenticated");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return res.json();
}

/**
 * SSE streaming fetch for chat. Returns a ReadableStream reader (D47).
 */
export async function apiStream(
  path: string,
  body: Record<string, unknown>
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("engram_token") : null;

  const res = await fetch(getApiUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("engram_token");
      window.location.href = "/login";
    }
    throw new Error("Not authenticated");
  }

  if (!res.body) {
    throw new Error("No response body");
  }

  return res.body.getReader();
}
