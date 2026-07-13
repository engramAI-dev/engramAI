import { describe, expect, it } from "vitest";
import { workspacePathSegment } from "./workspace-context";

describe("workspacePathSegment", () => {
  it("slugifies a workspace name for the terminal path", () => {
    expect(workspacePathSegment("Acme's Workspace")).toBe("acme-s-workspace");
  });

  it("falls back to the generic segment when unresolved", () => {
    expect(workspacePathSegment(undefined)).toBe("workspace");
  });

  it("falls back when the name has no usable characters", () => {
    expect(workspacePathSegment("!!!")).toBe("workspace");
  });

  it("trims leading and trailing separators", () => {
    expect(workspacePathSegment("  team ω engram  ")).toBe("team-engram");
  });
});
