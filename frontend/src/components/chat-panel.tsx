"use client";

/**
 * A15 — Chat interface with SSE streaming.
 * Uses B's OutputPanel (D49) for assistant message rendering.
 */

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { OutputPanel, type OutputPanelSource } from "@/components/output-panel";
import { useChat } from "@/lib/chat-context";

function sourcesToOutputPanelSources(
  sources: { chunk_id: string; document_id: string; document_title: string; file_path: string | null; source: string; url: string; relevance_score: number; content_preview: string }[]
): OutputPanelSource[] {
  return sources.map((s) => ({
    chunkId: s.chunk_id,
    documentId: s.document_id,
    documentTitle: s.document_title,
    filePath: s.file_path,
    source: s.source as "github" | "notion",
    url: s.url,
    relevanceScore: s.relevance_score,
    contentPreview: s.content_preview,
  }));
}

export function ChatPanel() {
  const [input, setInput] = useState("");
  const { messages, isStreaming, sendMessage } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  }

  return (
    <main className="flex flex-1 flex-col">
      <div className="flex h-14 items-center border-b px-6">
        <h2 className="font-medium">Chat</h2>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.length === 0 ? (
            <p className="py-20 text-center text-muted-foreground">
              Ask a question about your codebase or documentation.
            </p>
          ) : (
            messages.map((msg) =>
              msg.role === "user" ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-primary-foreground">
                    <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                  </div>
                </div>
              ) : (
                <div key={msg.id} className="flex justify-start">
                  <div className="max-w-full">
                    <OutputPanel
                      message={msg.content}
                      sources={sourcesToOutputPanelSources(msg.sources)}
                      intent="question"
                      isGenerating={isStreaming && msg === messages[messages.length - 1] && !msg.content}
                    />
                  </div>
                </div>
              )
            )
          )}
        </div>
      </div>

      <div className="border-t p-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-3xl gap-2"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your code or docs..."
            className="min-h-[44px] flex-1 resize-none"
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            disabled={isStreaming}
          />
          <Button type="submit" disabled={!input.trim() || isStreaming}>
            {isStreaming ? "..." : "Send"}
          </Button>
        </form>
      </div>
    </main>
  );
}
