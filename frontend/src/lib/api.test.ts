import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getOutput, listOutputs } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  if (typeof window !== "undefined") {
    window.localStorage.clear();
  }
});

function mockJsonResponse(body: unknown, init: ResponseInit = { status: 200 }): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
}

describe("api.listOutputs", () => {
  it("hits /api/outputs with no query when no params given", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ outputs: [], total: 0, page: 1 }),
    );
    await listOutputs();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/outputs",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("includes type, page, limit in the query string", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ outputs: [], total: 0, page: 2 }),
    );
    await listOutputs({ type: "summary", page: 2, limit: 50 });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("type=summary");
    expect(url).toContain("page=2");
    expect(url).toContain("limit=50");
  });

  it("attaches the bearer token from localStorage when present", async () => {
    window.localStorage.setItem("engram_token", "test-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ outputs: [], total: 0, page: 1 }),
    );
    await listOutputs();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("throws ApiError with detail from response body on non-2xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ detail: "Not authenticated" }, { status: 401 }),
    );
    await expect(listOutputs()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Not authenticated",
    });
  });
});

describe("api.getOutput", () => {
  it("hits /api/outputs/{id}", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        id: "abc",
        type: "code_snippet",
        title: "t",
        content: "c",
        metadata: {
          language: null,
          file_path_suggestion: null,
          source_message_id: "m",
          source_conversation_id: "c",
        },
        created_at: "2026-01-01T00:00:00Z",
      }),
    );
    await getOutput("abc");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/outputs/abc");
  });

  it("propagates ApiError with status on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ detail: "Output not found" }, { status: 404 }),
    );
    await expect(getOutput("missing")).rejects.toBeInstanceOf(ApiError);
  });
});
