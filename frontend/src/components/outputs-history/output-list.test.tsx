import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutputList } from "./output-list";
import type { OutputListItem } from "@/lib/api";

function item(overrides: Partial<OutputListItem> = {}): OutputListItem {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    type: "code_snippet",
    title: "Auth middleware",
    preview: "def verify_token(token: str) -> dict: ...",
    created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    ...overrides,
  };
}

describe("OutputList", () => {
  it("renders the empty state when no items", () => {
    render(<OutputList items={[]} />);
    expect(screen.getByTestId("outputs-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("outputs-list")).not.toBeInTheDocument();
  });

  it("renders one row per item with title, preview, type label and link", () => {
    const items = [
      item(),
      item({ id: "22", type: "summary", title: "Plan recap", preview: "We decided to ..." }),
    ];
    render(<OutputList items={items} />);
    const rows = screen.getAllByTestId("outputs-row");
    expect(rows).toHaveLength(2);

    expect(within(rows[0]).getByText("Auth middleware")).toBeInTheDocument();
    expect(within(rows[0]).getByText(/def verify_token/)).toBeInTheDocument();
    expect(within(rows[0]).getByText("Code")).toBeInTheDocument();
    const link0 = within(rows[0]).getByRole("link");
    expect(link0).toHaveAttribute(
      "href",
      "/outputs/11111111-1111-1111-1111-111111111111",
    );

    expect(within(rows[1]).getByText("Plan recap")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Summary")).toBeInTheDocument();
  });

  it("formats recent timestamps as relative", () => {
    const items = [item({ created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString() })];
    render(<OutputList items={items} />);
    expect(screen.getByText(/m ago/)).toBeInTheDocument();
  });
});
