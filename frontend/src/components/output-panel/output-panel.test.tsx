import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OutputPanel, type OutputPanelSource } from "../output-panel";

function source(overrides: Partial<OutputPanelSource> = {}): OutputPanelSource {
  return {
    chunkId: "c1",
    documentId: "d1",
    documentTitle: "middleware.py",
    filePath: "backend/api/middleware.py",
    source: "github",
    url: "https://github.com/x/y/blob/main/backend/api/middleware.py",
    relevanceScore: 0.9,
    contentPreview: "def get_current_user(): ...",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("OutputPanel", () => {
  it("renders prose markdown — paragraph, list, link", () => {
    const md = "Hello **world**\n\n- one\n- two\n\n[Engram](https://example.com)";
    render(<OutputPanel message={md} sources={[]} intent="explain" isGenerating={false} />);
    expect(screen.getByText("world")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const link = screen.getByRole("link", { name: "Engram" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders a fenced code block via Shiki", async () => {
    const md = "```python\ndef f():\n    return 1\n```";
    render(<OutputPanel message={md} sources={[]} intent="generate" isGenerating={false} />);
    expect(screen.getByTestId("code-block")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("shiki-output")).toBeInTheDocument();
    });
  });

  it("per-block copy button writes the code to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const md = "```python\nx = 1\n```";
    render(<OutputPanel message={md} sources={[]} intent="generate" isGenerating={false} />);
    const btn = screen.getByRole("button", { name: "Copy code" });
    await userEvent.click(btn);
    expect(writeText).toHaveBeenCalledWith("x = 1");
    await waitFor(() => expect(btn).toHaveTextContent("Copied"));
  });

  it("renders one citation per source with target=_blank", () => {
    const sources = [
      source(),
      source({ chunkId: "c2", documentTitle: "config.py", url: "https://github.com/x/y/blob/main/backend/config.py" }),
    ];
    render(<OutputPanel message="text" sources={sources} intent="explain" isGenerating={false} />);
    const footer = screen.getByTestId("citations");
    const links = within(footer).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveTextContent("middleware.py");
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(links[0]).toHaveAttribute("rel", "noopener noreferrer");
    expect(links[1]).toHaveTextContent("config.py");
  });

  it("intent=generate exposes data-intent for code-first layout", () => {
    render(<OutputPanel message="text" sources={[]} intent="generate" isGenerating={false} />);
    expect(screen.getByTestId("output-panel")).toHaveAttribute("data-intent", "generate");
    expect(screen.getByTestId("intent-badge")).toHaveTextContent("Generated code");
  });

  it("intent=explain exposes data-intent for prose-first layout", () => {
    render(<OutputPanel message="text" sources={[]} intent="explain" isGenerating={false} />);
    expect(screen.getByTestId("output-panel")).toHaveAttribute("data-intent", "explain");
    expect(screen.getByTestId("intent-badge")).toHaveTextContent("Explanation");
  });

  it("intent=question with empty sources omits the citations footer", () => {
    render(<OutputPanel message="just text" sources={[]} intent="question" isGenerating={false} />);
    expect(screen.queryByTestId("citations")).not.toBeInTheDocument();
    expect(screen.getByTestId("intent-badge")).toHaveTextContent("Answer");
  });

  it("intent=question with sources still shows the footer", () => {
    render(<OutputPanel message="text" sources={[source()]} intent="question" isGenerating={false} />);
    expect(screen.getByTestId("citations")).toBeInTheDocument();
  });

  it("isGenerating=true renders the indicator and partial markdown without crashing", () => {
    render(
      <OutputPanel
        message="partial **bold without close"
        sources={[]}
        intent="generate"
        isGenerating={true}
      />,
    );
    expect(screen.getByTestId("generating-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("output-panel")).toHaveAttribute("data-generating", "true");
  });

  it("unknown fenced language falls back to plain <pre> (no Shiki crash)", () => {
    const md = "```ruby\ndef f; 1; end\n```";
    render(<OutputPanel message={md} sources={[]} intent="generate" isGenerating={false} />);
    expect(screen.getByTestId("plain-pre")).toBeInTheDocument();
    expect(screen.queryByTestId("shiki-output")).not.toBeInTheDocument();
    expect(screen.getByText(/def f; 1; end/)).toBeInTheDocument();
  });

  it("empty sources omits the citation footer entirely", () => {
    render(<OutputPanel message="text" sources={[]} intent="explain" isGenerating={false} />);
    expect(screen.queryByTestId("citations")).not.toBeInTheDocument();
  });
});
