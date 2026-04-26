"use client";

/**
 * A17 — Context viewer. Shows source chunks from the current assistant message.
 */

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useChat } from "@/lib/chat-context";

export function ContextPanel() {
  const { currentSources } = useChat();

  return (
    <aside className="flex h-full w-80 min-h-0 flex-col border-l bg-muted/10">
      <div className="flex h-14 items-center px-4">
        <h3 className="text-sm font-medium text-muted-foreground">
          Sources{" "}
          {currentSources.length > 0 && (
            <span className="ml-1 text-xs">({currentSources.length})</span>
          )}
        </h3>
      </div>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 p-3">
        {currentSources.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Referenced sources will appear here when you ask a question.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {currentSources.map((source) => (
              <a
                key={source.chunk_id}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group rounded-lg border bg-background p-3 transition-colors hover:border-primary/50 hover:bg-muted/50"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium">
                      {source.document_title}
                    </p>
                    {source.file_path && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {source.file_path}
                      </p>
                    )}
                  </div>
                  <span className="shrink-0 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                    {Math.round(source.relevance_score * 100)}%
                  </span>
                </div>
                <p className="mt-1.5 line-clamp-3 text-xs text-muted-foreground">
                  {source.content_preview}
                </p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      source.source === "github"
                        ? "bg-green-500"
                        : "bg-blue-500"
                    }`}
                  />
                  <span className="text-[10px] text-muted-foreground">
                    {source.source}
                  </span>
                </div>
              </a>
            ))}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}
