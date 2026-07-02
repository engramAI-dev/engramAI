/**
 * A14 — API fetch wrapper with Bearer token.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

// --- Silent session renewal (Phase 1) ---------------------------------------
// Cookies carry the session; on a 401 we try one refresh (rotates the refresh
// cookie → new access cookie) and replay the request once. Concurrent 401s
// share a single in-flight refresh so we don't stampede /refresh.
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(getApiUrl("/api/auth/refresh"), {
      method: "POST",
      credentials: "include",
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function fetchWithRefresh(
  url: string,
  init: RequestInit,
): Promise<Response> {
  const withCreds: RequestInit = { ...init, credentials: "include" };
  const res = await fetch(url, withCreds);
  if (res.status !== 401) return res;
  const renewed = await refreshSession();
  if (!renewed) return res; // caller handles the 401
  return fetch(url, withCreds); // replay once with the new access cookie
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

  const res = await fetchWithRefresh(getApiUrl(path), {
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

  if (res.status === 204) return undefined as T;
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

  const res = await fetchWithRefresh(getApiUrl(path), {
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

// ---------------------------------------------------------------------------
// B-side: outputs API (B6b/B7/B9). Reuses apiFetch above so auth + base URL
// stay aligned with A's chat surface.
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type OutputType = "code_snippet" | "summary" | "report";

export interface OutputListItem {
  id: string;
  type: OutputType;
  title: string;
  preview: string;
  created_at: string;
}

export interface OutputListResponse {
  outputs: OutputListItem[];
  total: number;
  page: number;
}

export interface OutputResponse {
  id: string;
  type: OutputType;
  title: string;
  content: string;
  created_at: string;
  metadata: {
    language: string | null;
    file_path_suggestion: string | null;
    source_message_id: string;
    source_conversation_id: string;
  };
}

async function jsonOrThrow<T>(path: string): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("engram_token") : null;
  const res = await fetchWithRefresh(getApiUrl(path), {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listOutputs(params: {
  type?: OutputType;
  page?: number;
  limit?: number;
} = {}): Promise<OutputListResponse> {
  const qs = new URLSearchParams();
  if (params.type) qs.set("type", params.type);
  if (params.page) qs.set("page", String(params.page));
  if (params.limit) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return jsonOrThrow<OutputListResponse>(
    query ? `/api/outputs?${query}` : "/api/outputs",
  );
}

export async function getOutput(id: string): Promise<OutputResponse> {
  return jsonOrThrow<OutputResponse>(`/api/outputs/${id}`);
}

export async function generateOutput(
  messageId: string,
  outputType: OutputType,
): Promise<OutputResponse> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("engram_token") : null;
  const res = await fetchWithRefresh(getApiUrl("/api/outputs/generate"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message_id: messageId, output_type: outputType }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || `API error ${res.status}`);
  }
  return res.json() as Promise<OutputResponse>;
}
