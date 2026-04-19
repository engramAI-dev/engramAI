// B8 — Output panel (right side of /chat).
// Layer 1 (user-visible v1) per docs/v1/planning/partner-b-v1-plan.md.
// Design: docs/v1/planning/detailed/partner-b-b8-output-panel.md.

"use client";

import { Citations } from "./output-panel/citations";
import { Markdown } from "./output-panel/markdown";

export interface OutputPanelSource {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  filePath: string | null;
  source: "github" | "notion";
  url: string;
  relevanceScore: number;
  contentPreview: string;
}

export type OutputPanelIntent = "explain" | "generate" | "question";

export interface OutputPanelProps {
  message: string;
  sources: OutputPanelSource[];
  intent: OutputPanelIntent;
  isGenerating: boolean;
}

const INTENT_LABEL: Record<OutputPanelIntent, string> = {
  explain: "Explanation",
  generate: "Generated code",
  question: "Answer",
};

const INTENT_LAYOUT: Record<OutputPanelIntent, string> = {
  // generate: code-first. The post-processor (B3) puts the code block at the
  // top of the message, so prose flows below naturally.
  generate: "max-w-3xl space-y-3",
  // explain: prose-first, comfortable reading width.
  explain: "max-w-2xl space-y-3 leading-relaxed",
  // question: conversational; tighter, hides footer when no sources.
  question: "max-w-xl space-y-2 text-sm",
};

export function OutputPanel({ message, sources, intent, isGenerating }: OutputPanelProps) {
  return (
    <article
      data-testid="output-panel"
      data-intent={intent}
      data-generating={isGenerating ? "true" : "false"}
      className={`mx-auto px-4 py-3 ${INTENT_LAYOUT[intent]}`}
    >
      <header className="flex items-center gap-2 text-xs">
        <span
          data-testid="intent-badge"
          className="rounded-full border px-2 py-0.5 font-medium uppercase tracking-wide text-muted-foreground"
        >
          {INTENT_LABEL[intent]}
        </span>
        {isGenerating && (
          <span data-testid="generating-indicator" className="text-muted-foreground">
            generating…
          </span>
        )}
      </header>

      <Markdown>{message}</Markdown>

      {intent === "question" && sources.length === 0 ? null : (
        <Citations sources={sources} />
      )}
    </article>
  );
}
