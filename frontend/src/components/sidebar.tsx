"use client";

/**
 * A16 ��� Sidebar with conversation history + repo connect.
 */

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { useChat } from "@/lib/chat-context";
import { apiFetch } from "@/lib/api";
import { logout } from "@/lib/auth";

export function Sidebar() {
  const {
    conversations,
    currentConversationId,
    loadConversations,
    loadConversation,
    newChat,
  } = useChat();

  const [repoUrl, setRepoUrl] = useState("");
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!repoUrl.trim()) return;

    setIngestStatus("Queuing...");
    try {
      const result = await apiFetch<{ job_id: string; status: string }>(
        "/api/ingest/github",
        {
          method: "POST",
          body: JSON.stringify({ repo_url: repoUrl.trim() }),
        }
      );

      setIngestStatus("Processing...");
      // Poll status
      const pollInterval = setInterval(async () => {
        try {
          const status = await apiFetch<{
            status: string;
            progress: number;
            documents_indexed: number;
          }>(`/api/ingest/status/${result.job_id}`);

          if (status.status === "complete") {
            setIngestStatus(
              `Done! ${status.documents_indexed} files indexed.`
            );
            clearInterval(pollInterval);
            setTimeout(() => setIngestStatus(null), 3000);
            setRepoUrl("");
          } else if (status.status === "failed") {
            setIngestStatus("Failed");
            clearInterval(pollInterval);
          } else {
            setIngestStatus(
              `${status.status}... ${Math.round(status.progress * 100)}%`
            );
          }
        } catch {
          clearInterval(pollInterval);
          setIngestStatus("Error polling status");
        }
      }, 3000);
    } catch (err) {
      setIngestStatus(
        `Error: ${err instanceof Error ? err.message : "Unknown"}`
      );
    }
  }

  return (
    <aside className="flex w-64 flex-col border-r bg-muted/30">
      <div className="flex h-14 items-center px-4 font-semibold">Engram</div>
      <Separator />

      <div className="p-3">
        <Button
          variant="outline"
          className="w-full justify-start"
          onClick={newChat}
        >
          + New Chat
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3">
        <nav className="flex flex-col gap-1">
          {conversations.length === 0 ? (
            <p className="px-2 py-8 text-center text-sm text-muted-foreground">
              No conversations yet
            </p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => loadConversation(conv.id)}
                className={`rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted ${
                  conv.id === currentConversationId
                    ? "bg-muted font-medium"
                    : "text-muted-foreground"
                }`}
              >
                <span className="line-clamp-1">
                  {conv.title || "Untitled"}
                </span>
              </button>
            ))
          )}
        </nav>
      </ScrollArea>

      <Separator />

      {/* A16: Repo connect */}
      <div className="p-3">
        <form onSubmit={handleIngest} className="flex flex-col gap-2">
          <Input
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="github.com/owner/repo"
            className="text-xs"
          />
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={!repoUrl.trim() || !!ingestStatus}
          >
            {ingestStatus || "Index Repo"}
          </Button>
        </form>
      </div>

      <Separator />
      <div className="p-3">
        <Button
          variant="ghost"
          className="w-full justify-start text-sm"
          onClick={logout}
        >
          Sign out
        </Button>
      </div>
    </aside>
  );
}
