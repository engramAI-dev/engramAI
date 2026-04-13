"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";

export function ChatPanel() {
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    // TODO: Send message to API
    setInput("");
  }

  return (
    <main className="flex flex-1 flex-col">
      <div className="flex h-14 items-center border-b px-6">
        <h2 className="font-medium">Chat</h2>
      </div>
      <ScrollArea className="flex-1 p-6">
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {/* Messages will render here */}
          <p className="py-20 text-center text-muted-foreground">
            Ask a question about your codebase or documentation.
          </p>
        </div>
      </ScrollArea>
      <div className="border-t p-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-2xl gap-2"
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
          />
          <Button type="submit" disabled={!input.trim()}>
            Send
          </Button>
        </form>
      </div>
    </main>
  );
}
