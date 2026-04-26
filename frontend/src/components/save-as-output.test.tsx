import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SaveAsOutput } from "./save-as-output";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockJsonResponse(body: unknown, init: ResponseInit = { status: 200 }): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
}

const SAMPLE_OUTPUT = {
  id: "output-123",
  type: "summary" as const,
  title: "t",
  content: "c",
  metadata: {
    language: null,
    file_path_suggestion: null,
    source_message_id: "msg-1",
    source_conversation_id: "conv-1",
  },
  created_at: "2026-04-26T00:00:00Z",
};

describe("SaveAsOutput", () => {
  it("posts to /api/outputs/generate with the messageId and chosen type", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockJsonResponse(SAMPLE_OUTPUT));
    render(<SaveAsOutput messageId="msg-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Summary" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      message_id: "msg-1",
      output_type: "summary",
    });
  });

  it("renders a link to /outputs/{id} after saving", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse(SAMPLE_OUTPUT));
    render(<SaveAsOutput messageId="msg-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Code" }));
    const link = await screen.findByTestId("save-as-output-link");
    expect(link).toHaveAttribute("href", "/outputs/output-123");
  });

  it("shows an error message on non-2xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({ detail: "Message not found" }, { status: 400 }),
    );
    render(<SaveAsOutput messageId="msg-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Report" }));
    const err = await screen.findByTestId("save-as-output-error");
    expect(err.textContent).toContain("Message not found");
  });
});
