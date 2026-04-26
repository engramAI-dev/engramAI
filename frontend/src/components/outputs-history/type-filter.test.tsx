import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TypeFilter } from "./type-filter";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(""),
}));

afterEach(() => {
  pushMock.mockReset();
});

describe("TypeFilter", () => {
  it("renders four pills with the active one marked", () => {
    render(<TypeFilter active="summary" />);
    const pills = screen.getAllByRole("button");
    expect(pills).toHaveLength(4);
    const summary = screen.getByRole("button", { name: "Summary" });
    expect(summary).toHaveAttribute("data-active", "true");
    expect(summary).toHaveAttribute("aria-pressed", "true");
    const code = screen.getByRole("button", { name: "Code" });
    expect(code).toHaveAttribute("data-active", "false");
  });

  it("clicking 'All' removes the type param", async () => {
    render(<TypeFilter active="summary" />);
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(pushMock).toHaveBeenCalledWith("/outputs");
  });

  it("clicking a specific pill sets the type param and resets page", async () => {
    render(<TypeFilter active="all" />);
    await userEvent.click(screen.getByRole("button", { name: "Code" }));
    expect(pushMock).toHaveBeenCalledWith("/outputs?type=code_snippet");
  });
});
