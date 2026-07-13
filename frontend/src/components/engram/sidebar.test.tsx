import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./sidebar";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/auth", () => ({
  logout: vi.fn(),
}));

describe("Sidebar", () => {
  it("shows the active workspace name when provided", () => {
    render(<Sidebar workspaceName="acme's workspace" />);
    expect(screen.getByTestId("sidebar-workspace-name")).toHaveTextContent(
      "acme's workspace",
    );
  });

  it("falls back to a generic label without a workspace name", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar-workspace-name")).toHaveTextContent("workspace");
  });

  it("navigates back to the dashboard from the workspaces link", () => {
    render(<Sidebar workspaceName="acme's workspace" />);
    fireEvent.click(screen.getByTestId("sidebar-workspaces-link"));
    expect(push).toHaveBeenCalledWith("/dashboard");
  });
});
