"use client";

/**
 * A15 — Chat state context (D48: React context).
 * Manages messages, conversations, streaming state, and source chunks.
 */

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, apiStream } from "./api";

// Types matching the backend API contract
export interface SourceChunk {
  chunk_id: string;
  document_id: string;
  document_title: string;
  file_path: string | null;
  source: string;
  url: string;
  relevance_score: number;
  content_preview: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: SourceChunk[];
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  message_count: number;
  updated_at: string;
}

interface ChatState {
  messages: Message[];
  conversations: Conversation[];
  currentConversationId: string | null;
  isStreaming: boolean;
  currentSources: SourceChunk[];
  sendMessage: (text: string) => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  loadConversations: () => Promise<void>;
  newChat: () => void;
}

const ChatContext = createContext<ChatState | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSources, setCurrentSources] = useState<SourceChunk[]>([]);

  const loadConversations = useCallback(async () => {
    const data = await apiFetch<{
      conversations: Conversation[];
      total: number;
    }>("/api/chat/conversations");
    setConversations(data.conversations);
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const data = await apiFetch<{ messages: Message[] }>(
      `/api/chat/conversations/${id}/messages`
    );
    setMessages(data.messages);
    setCurrentConversationId(id);
    // Set sources from last assistant message
    const lastAssistant = [...data.messages]
      .reverse()
      .find((m) => m.role === "assistant");
    if (lastAssistant) {
      setCurrentSources(lastAssistant.sources);
    }
  }, []);

  const newChat = useCallback(() => {
    setMessages([]);
    setCurrentConversationId(null);
    setCurrentSources([]);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      // Add user message optimistically
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        sources: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
      setCurrentSources([]);

      // Placeholder for streaming assistant response
      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        sources: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      try {
        const reader = await apiStream("/api/chat/", {
          message: text,
          conversation_id: currentConversationId,
        });

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const json = line.slice(6).trim();
            if (!json) continue;

            try {
              const event = JSON.parse(json);

              if (event.type === "text") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + event.content }
                      : m
                  )
                );
              } else if (event.type === "sources") {
                const sources = event.content as SourceChunk[];
                setCurrentSources(sources);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, sources } : m
                  )
                );
              } else if (event.type === "done") {
                setCurrentConversationId(event.conversation_id);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, id: event.message_id }
                      : m
                  )
                );
              } else if (event.type === "error") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: `Error: ${event.content}` }
                      : m
                  )
                );
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
                }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
        loadConversations();
      }
    },
    [currentConversationId, loadConversations]
  );

  return (
    <ChatContext.Provider
      value={{
        messages,
        conversations,
        currentConversationId,
        isStreaming,
        currentSources,
        sendMessage,
        loadConversation,
        loadConversations,
        newChat,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat(): ChatState {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within ChatProvider");
  return ctx;
}
