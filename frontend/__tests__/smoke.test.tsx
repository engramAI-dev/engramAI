import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function Hello({ name }: { name: string }) {
  return <h1>Hello, {name}</h1>;
}

describe("frontend test infra (B8-pre)", () => {
  it("renders a component and queries the DOM", () => {
    render(<Hello name="Engram" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Hello, Engram");
  });
});
