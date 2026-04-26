import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Pagination } from "./pagination";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(""),
}));

afterEach(() => {
  pushMock.mockReset();
});

describe("Pagination", () => {
  it("shows current page, total pages, and total count", () => {
    render(<Pagination page={2} limit={20} total={45} />);
    expect(screen.getByTestId("page-label")).toHaveTextContent("Page 2 of 3");
    expect(screen.getByTestId("page-label")).toHaveTextContent("45 total");
  });

  it("disables Prev on page 1", () => {
    render(<Pagination page={1} limit={20} total={45} />);
    expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled();
  });

  it("disables Next on the last page", () => {
    render(<Pagination page={3} limit={20} total={45} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("clicking Next pushes the next page", async () => {
    render(<Pagination page={1} limit={20} total={45} />);
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(pushMock).toHaveBeenCalledWith("/outputs?page=2");
  });

  it("clicking Prev going back to 1 drops the page param", async () => {
    render(<Pagination page={2} limit={20} total={45} />);
    await userEvent.click(screen.getByRole("button", { name: "Prev" }));
    expect(pushMock).toHaveBeenCalledWith("/outputs");
  });

  it("renders 'Page 1 of 1' when total is 0", () => {
    render(<Pagination page={1} limit={20} total={0} />);
    expect(screen.getByTestId("page-label")).toHaveTextContent("Page 1 of 1");
  });
});
