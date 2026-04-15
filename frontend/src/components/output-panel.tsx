// B8 — Output panel (right side of /chat).
// Layer 1 (user-visible v1) per docs/v1/planning/partner-b-v1-plan.md.
// TODO [B8]: syntax highlight (Shiki/Prism), markdown, copy/download, citations.

"use client";

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

export interface OutputPanelProps {
  message: string;
  sources: OutputPanelSource[];
  intent: "explain" | "generate" | "question";
  isGenerating: boolean;
}

export function OutputPanel(_props: OutputPanelProps) {
  // TODO [B8]: render formatted output with syntax highlighting + citations.
  return <div data-testid="output-panel" />;
}
