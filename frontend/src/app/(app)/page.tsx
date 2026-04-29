"use client";

/**
 * Workspace (chat) page — v3 "Datasheet / CRT" terminal aesthetic.
 * Pure monospace, ASCII furniture, bracket affordances.
 */

import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import { useChat, type Message, type SourceChunk } from "@/lib/chat-context";
import { apiFetch } from "@/lib/api";
import { TopBar } from "@/components/engram/top-bar";
import { V3Tag, V3Btn, V3StatusBar, V3Hr } from "@/components/engram/components";

// -------------------------------------------------------------------
// ConversationFromQuery — loads a conversation from ?c= param
// -------------------------------------------------------------------

function ConversationFromQuery() {
  const params = useSearchParams();
  const { loadConversation } = useChat();
  const lastLoaded = useRef<string | null>(null);

  useEffect(() => {
    const requested = params.get("c");
    if (!requested || lastLoaded.current === requested) return;
    lastLoaded.current = requested;
    loadConversation(requested).catch(() => {
      lastLoaded.current = null;
    });
  }, [params, loadConversation]);

  return null;
}

// -------------------------------------------------------------------
// Inline citation button — [n] bracket style
// -------------------------------------------------------------------

function CitRef({
  n,
  hot,
  onEnter,
  onLeave,
}: {
  n: number;
  hot: boolean;
  onEnter: () => void;
  onLeave: () => void;
}) {
  return (
    <button
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      style={{
        display: "inline",
        padding: "0 4px",
        margin: "0 1px",
        background: hot ? "var(--accent)" : "transparent",
        color: hot ? "var(--bg)" : "var(--accent)",
        border: `1px solid ${hot ? "var(--accent)" : "var(--ink-4)"}`,
        borderRadius: 0,
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 11,
      }}
    >
      [{n}]
    </button>
  );
}

// -------------------------------------------------------------------
// Detect intent from message content (heuristic)
// -------------------------------------------------------------------

type Intent = "explain" | "generate" | "question";

function detectIntent(content: string): Intent {
  const lower = content.toLowerCase();
  if (lower.includes("```") || lower.includes("here's a") || lower.includes("here is a")) {
    return "generate";
  }
  if (lower.includes("because") || lower.includes("this works by") || lower.includes("the reason")) {
    return "explain";
  }
  return "question";
}

// -------------------------------------------------------------------
// Render inline citations within text
// -------------------------------------------------------------------

function renderTextWithCitations(
  text: string,
  hotCite: number | null,
  setHotCite: (n: number | null) => void,
): ReactNode[] {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const n = parseInt(match[1], 10);
      return (
        <CitRef
          key={i}
          n={n}
          hot={hotCite === n}
          onEnter={() => setHotCite(n)}
          onLeave={() => setHotCite(null)}
        />
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// -------------------------------------------------------------------
// Assistant content renderer — monospace prose + code blocks
// -------------------------------------------------------------------

function AssistantContent({
  content,
  hotCite,
  setHotCite,
}: {
  content: string;
  hotCite: number | null;
  setHotCite: (n: number | null) => void;
}) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let codeBlock: string[] | null = null;
  let codeLang = "";

  for (let idx = 0; idx < lines.length; idx++) {
    const line = lines[idx];

    if (line.startsWith("```")) {
      if (codeBlock === null) {
        codeBlock = [];
        codeLang = line.slice(3).trim();
      } else {
        const codeSnippet = codeBlock.join("\n");
        blocks.push(
          <div key={`code-${idx}`} style={{ margin: "12px 0", border: "1px solid var(--ink)" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 10px",
                borderBottom: "1px solid var(--ink)",
                background: "var(--surface)",
                fontSize: 10.5,
                fontFamily: "var(--font-mono)",
              }}
            >
              <span style={{ color: "var(--ink-3)" }}>{codeLang || "code"}</span>
              <span style={{ flex: 1 }} />
              <V3Btn size="sm" onClick={(e) => { navigator.clipboard.writeText(codeSnippet); const btn = e.currentTarget; btn.textContent = "copied!"; setTimeout(() => { btn.textContent = "copy"; }, 1500); }}>copy</V3Btn>
            </div>
            <pre
              style={{
                margin: 0,
                padding: "10px 14px",
                fontSize: 12,
                lineHeight: 1.65,
                color: "var(--ink-2)",
                fontFamily: "var(--font-mono)",
                overflowX: "auto",
                background: "var(--surface)",
              }}
            >
              {codeBlock.join("\n")}
            </pre>
          </div>,
        );
        codeBlock = null;
        codeLang = "";
      }
      continue;
    }

    if (codeBlock !== null) {
      codeBlock.push(line);
      continue;
    }

    // Section comment heading
    if (line.startsWith("## ") || line.startsWith("### ")) {
      const text = line.replace(/^#+\s+/, "");
      blocks.push(
        <div
          key={`h-${idx}`}
          style={{
            margin: "14px 0 6px",
            fontSize: 10.5,
            fontFamily: "var(--font-mono)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--ink)",
          }}
        >
          {"// "}{text}
        </div>,
      );
      continue;
    }

    // Callout / warning
    if (line.startsWith("> ")) {
      const text = line.slice(2);
      blocks.push(
        <div
          key={`callout-${idx}`}
          style={{
            margin: "8px 0",
            display: "flex",
            gap: 8,
            alignItems: "flex-start",
          }}
        >
          <V3Tag tone="warn">[WARN]</V3Tag>
          <span style={{ fontSize: 12.5, color: "var(--warn)" }}>
            {text.replace(/^\*\*(Warning|Note)\*\*:?\s*/i, "")}
          </span>
        </div>,
      );
      continue;
    }

    if (!line.trim()) continue;

    blocks.push(
      <p
        key={`p-${idx}`}
        style={{
          margin: "0 0 8px",
          color: "var(--ink-2)",
          fontSize: 12.5,
          lineHeight: 1.7,
          fontFamily: "var(--font-mono)",
        }}
      >
        {renderTextWithCitations(line, hotCite, setHotCite)}
      </p>,
    );
  }

  return <>{blocks}</>;
}

// -------------------------------------------------------------------
// User message — right-aligned, bordered, no rounded corners
// -------------------------------------------------------------------

function UserBubble({ msg }: { msg: Message }) {
  const time = new Date(msg.created_at);
  const ts = `${time.getHours().toString().padStart(2, "0")}:${time.getMinutes().toString().padStart(2, "0")}`;

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 4,
          justifyContent: "flex-end",
        }}
      >
        <span
          style={{
            fontSize: 10.5,
            fontFamily: "var(--font-mono)",
            color: "var(--ink-4)",
          }}
        >
          {ts}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            maxWidth: "80%",
            padding: "10px 14px",
            border: "1px solid var(--ink)",
            borderRadius: 0,
            fontSize: 13.5,
            lineHeight: 1.5,
            fontFamily: "var(--font-mono)",
            color: "var(--ink)",
          }}
        >
          {msg.content}
        </div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------
// Assistant message — left-aligned with intent tag
// -------------------------------------------------------------------


// -------------------------------------------------------------------
// Save as Output menu — calls POST /outputs/generate
// -------------------------------------------------------------------

function SaveAsOutputMenu({ messageId }: { messageId: string }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const save = useCallback(
    (outputType: string) => {
      setSaving(true);
      apiFetch<{ id: string; title: string }>("/api/outputs/generate", {
        method: "POST",
        body: JSON.stringify({ message_id: messageId, output_type: outputType }),
      })
        .then((data) => {
          setSaved(data.id);
          setSaving(false);
          setOpen(false);
        })
        .catch(() => {
          setSaving(false);
        });
    },
    [messageId],
  );

  if (saved) {
    return (
      <V3Btn
        size="sm"
        onClick={() => window.open(`/outputs/${saved}`, "_self")}
        style={{ color: "var(--accent)" }}
      >
        saved {"→"} view
      </V3Btn>
    );
  }

  if (!open) {
    return (
      <V3Btn size="sm" onClick={() => setOpen(true)}>
        {saving ? "saving..." : "save as"}
      </V3Btn>
    );
  }

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <V3Btn size="sm" onClick={() => save("code_snippet")}>code</V3Btn>
      <V3Btn size="sm" onClick={() => save("summary")}>summary</V3Btn>
      <V3Btn size="sm" onClick={() => save("report")}>report</V3Btn>
      <V3Btn size="sm" variant="ghost" onClick={() => setOpen(false)}>{"×"}</V3Btn>
    </div>
  );
}

function AssistantMessage({
  msg,
  isStreamingThis,
  hotCite,
  setHotCite,
}: {
  msg: Message;
  isStreamingThis: boolean;
  hotCite: number | null;
  setHotCite: (n: number | null) => void;
}) {
  const intent = detectIntent(msg.content);

  return (
    <div style={{ marginBottom: 24 }}>
      {/* Header tags */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <V3Tag tone="acc">{intent}</V3Tag>
        {msg.sources.length > 0 && (
          <V3Tag>top-{msg.sources.length} retrieved</V3Tag>
        )}
        {isStreamingThis && (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--accent)",
              animation: "egPulse 1.1s ease-in-out infinite",
            }}
          >
            {"\u2588"}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{ fontSize: 12.5, lineHeight: 1.7, color: "var(--ink-2)" }}>
        {msg.content ? (
          <>
            <span style={{ color: "var(--accent)" }}>{">"}</span>{" "}
            <AssistantContent content={msg.content} hotCite={hotCite} setHotCite={setHotCite} />
          </>
        ) : isStreamingThis ? (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              color: "var(--accent)",
              animation: "egPulse 1.1s ease-in-out infinite",
            }}
          >
            {"\u2588"}
          </span>
        ) : null}
      </div>



      {/* Actions */}
      {!isStreamingThis && msg.content && (
        <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
          <V3Btn size="sm" onClick={(e) => { navigator.clipboard.writeText(msg.content); const btn = e.currentTarget; btn.textContent = "copied!"; setTimeout(() => { btn.textContent = "copy"; }, 1500); }}>copy</V3Btn>
          <SaveAsOutputMenu messageId={msg.id} />
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------
// Retrieval tree — right panel, ASCII tree with block-char bars
// -------------------------------------------------------------------

function RetrievalTree({
  sources,
  hotCite,
  setHotCite,
}: {
  sources: SourceChunk[];
  hotCite: number | null;
  setHotCite: (n: number | null) => void;
}) {
  return (
    <aside
      style={{
        overflow: "auto",
        padding: 0,
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        borderLeft: "1px solid var(--ink)",
        width: "100%",
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--ink)",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10.5,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--ink-3)",
          }}
        >
          retrieval
        </span>
        <span style={{ flex: 1 }} />
        <V3Tag tone="ok">k={sources.length || 10}</V3Tag>
      </div>

      {/* Query info */}
      <pre
        style={{
          margin: 0,
          padding: "12px 14px",
          fontSize: 11,
          lineHeight: 1.65,
          color: "var(--ink-2)",
          fontFamily: "var(--font-mono)",
          borderBottom: "1px solid var(--line, var(--ink-4))",
          whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}
      >
        {`semantic search\n\u2514\u2500 ${sources.length} chunks · nomic-embed-v1.5`}
      </pre>

      {/* Tree items */}
      <div style={{ padding: "8px 0", flex: 1, overflow: "auto" }}>
        {sources.length === 0 ? (
          <div
            style={{
              padding: "32px 14px",
              textAlign: "center",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--ink-4)",
            }}
          >
            no retrieval results yet
          </div>
        ) : (
          sources.map((c, i) => {
            const last = i === sources.length - 1;
            const n = i + 1;
            const isGh = c.source === "github";
            const rel = c.relevance_score;
            const relPct = Math.round(rel * 100);
            const filledBars = Math.round(rel * 10);

            return (
              <button
                key={c.chunk_id}
                onMouseEnter={() => setHotCite(n)}
                onMouseLeave={() => setHotCite(null)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "6px 14px",
                  background: hotCite === n ? "var(--accent-soft, rgba(255,160,0,0.08))" : "transparent",
                  border: "none",
                  borderLeft: `2px solid ${hotCite === n ? "var(--accent)" : "transparent"}`,
                  cursor: "pointer",
                  fontFamily: "var(--font-mono)",
                  borderRadius: 0,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, flexWrap: "wrap" }}>
                  <span style={{ color: "var(--ink-4)" }}>{last ? "\u2514\u2500" : "\u251C\u2500"}</span>
                  <span
                    style={{
                      display: "inline-flex",
                      width: 22,
                      height: 16,
                      background: "var(--ink)",
                      color: "var(--bg)",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 10,
                      fontWeight: 600,
                    }}
                  >
                    {String(n).padStart(2, "0")}
                  </span>
                  <span
                    style={{
                      color: isGh ? "var(--ink)" : "var(--warn)",
                      fontSize: 10,
                    }}
                  >
                    {isGh ? "git" : "ntn"}
                  </span>
                  <span
                    style={{
                      flex: 1,
                      overflow: "hidden", overflowWrap: "break-word",
                      
                      whiteSpace: "normal",
                      color: "var(--ink)",
                    }}
                  >
                    {c.url ? (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: "var(--accent)", textDecoration: "none" }}
                        onMouseEnter={(e) => { e.currentTarget.style.textDecoration = "underline"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.textDecoration = "none"; }}
                      >
                        {c.file_path || c.document_title}
                      </a>
                    ) : (
                      c.file_path || c.document_title
                    )}
                  </span>
                  <span
                    style={{
                      color: "var(--ink)",
                      fontWeight: 600,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {relPct}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    paddingLeft: 26, flexWrap: "wrap",
                    marginTop: 2,
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10.5,
                      color: "var(--ink-4)",
                    }}
                  >
                    {c.document_title}
                  </span>
                  <span style={{ flex: 1 }} />
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--ink-3)",
                      letterSpacing: 0, whiteSpace: "nowrap",
                    }}
                  >
                    rel {"█".repeat(filledBars)}{"░".repeat(10 - filledBars)} {relPct}%
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Vec info */}
      {sources.length > 0 && (
        <div
          style={{
            padding: "10px 14px",
            borderTop: "1px solid var(--ink)",
            fontSize: 10,
            color: "var(--ink-4)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {sources.length} sources retrieved
        </div>
      )}
    </aside>
  );
}

// -------------------------------------------------------------------
// Chat composer — $ prompt + underline input + [ send ] button
// -------------------------------------------------------------------

function ChatComposer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div style={{ padding: "0 22px 0" }}>
      <V3Hr />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          border: "1px solid var(--ink)",
          height: 32,
          marginTop: 8,
          marginBottom: 8,
        }}
      >
        <span
          style={{
            color: "var(--accent)",
            padding: "0 10px",
            borderRight: "1px solid var(--ink)",
            height: "100%",
            display: "inline-flex",
            alignItems: "center",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
          }}
        >
          $
        </span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="ask about your code or docs..."
          disabled={disabled}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontFamily: "var(--font-mono)",
            fontSize: 12.5,
            padding: "0 10px",
            color: "var(--ink)",
            opacity: disabled ? 0.5 : 1,
          }}
        />
        <V3Btn
          variant="acc"
          size="sm"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          style={{
            borderTop: 0,
            borderBottom: 0,
            borderRight: 0,
            height: "100%",
            borderRadius: 0,
          }}
        >
          SEND {"\u21B5"}
        </V3Btn>
      </div>
      <div
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 8,
          justifyContent: "flex-end",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10.5,
            color: "var(--ink-4)",
          }}
        >
          {"\u2191"}/{"\u2193"} history {"·"} {"\u2318"}{"\u23CE"} send
        </span>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------
// Empty state
// -------------------------------------------------------------------

function EmptyState() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        flex: 1,
        padding: 48,
        fontFamily: "var(--font-mono)",
      }}
    >
      <pre
        style={{
          fontSize: 11,
          lineHeight: 1.7,
          color: "var(--ink-3)",
          textAlign: "center",
          margin: "0 0 16px",
        }}
      >
{`engram v0.1 · memory core
loaded modules: chat retrieval ingestion outputs
status:         operational`}
      </pre>
      <span style={{ fontSize: 12.5, color: "var(--ink-2)" }}>
        {">"} ask about your code or docs
      </span>
    </div>
  );
}

// -------------------------------------------------------------------
// Main workspace page
// -------------------------------------------------------------------

export default function WorkspacePage() {
  const { messages, isStreaming, currentSources, sendMessage } = useChat();
  const [hotCite, setHotCite] = useState<number | null>(null);
  const [retrievalWidth, setRetrievalWidth] = useState(380);
  const draggingRetrieval = useRef(false);

  const handleRetrievalDragStart = useCallback(() => {
    draggingRetrieval.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRetrieval.current) return;
      const w = Math.max(250, Math.min(600, window.innerWidth - e.clientX));
      setRetrievalWidth(w);
    };
    const handleMouseUp = () => {
      draggingRetrieval.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, []);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(
    (text: string) => {
      sendMessage(text).catch(() => {
        /* error shown inline */
      });
    },
    [sendMessage],
  );

  // Find last assistant index for streaming indicator
  const lastAssistantIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg)" }}>
      <Suspense fallback={null}>
        <ConversationFromQuery />
      </Suspense>

      <TopBar
        path="engram@core:~/workspace$ ask"
        right={
          <>
            <span style={{ color: "var(--accent)" }}>{"\u25CF"}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)", marginRight: 8 }}>
              {" "}rec
            </span>
          </>
        }
      />

      <div style={{ flex: 1, width: "100%", display: "grid", gridTemplateColumns: currentSources.length > 0 ? `1fr 4px ${retrievalWidth}px` : "1fr", overflow: "hidden", minHeight: 0, background: currentSources.length > 0 ? "var(--surface)" : "var(--bg)" }}>
        {/* Main chat column */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div
              ref={scrollRef}
              style={{
                flex: 1,
                overflow: "auto",
                padding: "16px 22px",
              }}
            >
              <div style={{ maxWidth: 720 }}>
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <UserBubble key={m.id} msg={m} />
                  ) : (
                    <AssistantMessage
                      key={m.id}
                      msg={m}
                      isStreamingThis={isStreaming && i === lastAssistantIdx}
                      hotCite={hotCite}
                      setHotCite={setHotCite}
                    />
                  ),
                )}
              </div>
            </div>
          )}

          <ChatComposer onSend={handleSend} disabled={isStreaming} />
        </div>

        {/* Drag handle for retrieval panel */}
        {currentSources.length > 0 && (
          <div
            onMouseDown={handleRetrievalDragStart}
            style={{ cursor: "col-resize", background: "var(--bg)" }}
          />
        )}

        {/* Right rail — retrieval tree */}
        {currentSources.length > 0 && (
          <RetrievalTree
            sources={currentSources}
            hotCite={hotCite}
            setHotCite={setHotCite}
          />
        )}
      </div>

      <V3StatusBar
        items={[
          <span key="online">
            <span style={{ color: "var(--accent)" }}>{"\u25CF"}</span> ONLINE
          </span>,
          `${messages.length} msgs`,
          `${currentSources.length} sources`,
          `${messages.filter(m => m.role === "assistant").length} responses`,
        ]}
      />
    </div>
  );
}
