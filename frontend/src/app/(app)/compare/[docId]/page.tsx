"use client";

import React, { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { V3TitleBar, V3StatusBar } from "@/components/engram/components";
import { apiFetch } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface DocumentDetail {
  id: string;
  title: string;
  source: string;
  repo: string | null;
  file_path: string | null;
  url: string | null;
  language: string | null;
  indexed_at: string | null;
  chunks: { id: string; content: string; start_line: number | null; end_line: number | null; chunk_type: string | null }[];
}

interface RelatedDoc {
  title: string;
  source: string;
  file_path: string | null;
  content: string;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ComparePage({
  params,
}: {
  params: Promise<{ docId: string }>;
}) {
  const { docId } = use(params);
  const router = useRouter();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [related, setRelated] = useState<RelatedDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        // Fetch the document
        const docData = await apiFetch<DocumentDetail>(`/api/documents/${docId}`);
        if (cancelled) return;
        setDoc(docData);

        // Try to find a related document from the other source
        const otherSource = docData.source === "github" ? "notion" : "github";
        const searchQuery = docData.title || docData.file_path || "";

        if (searchQuery) {
          const searchResult = await apiFetch<{ chunks: { document_title: string; file_path: string | null; source: string; content_preview: string }[] }>(
            `/api/knowledge/search?q=${encodeURIComponent(searchQuery)}&top_k=1&source=${otherSource}`
          );
          if (!cancelled && searchResult.chunks.length > 0) {
            const match = searchResult.chunks[0];
            setRelated({
              title: match.document_title,
              source: match.source,
              file_path: match.file_path,
              content: match.content_preview,
            });
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [docId]);

  if (loading) {
    return (
      <div className="v3-screen v3-scan">
        <V3TitleBar path={`engram@core:~/diff$ compare ${docId.slice(0, 8)}`} />
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ink-4)", fontSize: 12 }}>
          loading document...
        </div>
        <V3StatusBar items={["loading"]} />
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="v3-screen v3-scan">
        <V3TitleBar path={`engram@core:~/diff$ compare ${docId.slice(0, 8)}`} />
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--err)", fontSize: 12 }}>
          {error || "document not found"}
        </div>
        <V3StatusBar items={["error"]} />
      </div>
    );
  }

  const docContent = doc.chunks.map((c) => c.content).join("\n\n");
  const isCode = doc.source === "github";

  return (
    <div className="v3-screen v3-scan" style={{ flexDirection: "row" }}>
      <div className="v3-frame" style={{ flex: 1, border: "none", borderLeft: "1px solid var(--ink)" }}>
        <V3TitleBar
          path={`engram@core:~/diff$ ${doc.title}`}
          right={
            <>
              <button
                onClick={() => router.push("/compare")}
                style={{
                  background: "transparent",
                  border: "1px solid var(--bg)",
                  color: "var(--bg)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  padding: "2px 8px",
                  cursor: "pointer",
                }}
              >
                {"\u2190 back"}
              </button>
            </>
          }
        />

        {/* info bar */}
        <div style={{
          padding: "8px 14px", borderBottom: "1px solid var(--ink)",
          display: "flex", gap: 12, alignItems: "center", fontSize: 11, background: "var(--surface)",
        }}>
          <span style={{ color: isCode ? "var(--accent)" : "var(--warn)" }}>
            {isCode ? "git" : "ntn"}
          </span>
          <span>{doc.file_path || doc.title}</span>
          <span style={{ color: "var(--ink-4)" }}>{doc.repo || ""}</span>
          {related && (
            <>
              <span style={{ flex: 1, textAlign: "center", color: "var(--ink-4)" }}>{"\u2194"}</span>
              <span>{related.file_path || related.title}</span>
              <span style={{ color: related.source === "github" ? "var(--accent)" : "var(--warn)" }}>
                {related.source === "github" ? "git" : "ntn"}
              </span>
            </>
          )}
        </div>

        {/* split view */}
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: related ? "1fr 1fr" : "1fr", overflow: "hidden", minHeight: 0 }}>
          {/* left: this document */}
          <div className="v3-scroll" style={{ overflow: "auto", borderRight: related ? "1px solid var(--ink)" : "none" }}>
            <div style={{ padding: "12px 18px" }}>
              <h3 style={{ fontSize: 14, margin: "0 0 12px" }}>{doc.file_path || doc.title}</h3>
              <pre style={{
                fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.75,
                color: "var(--ink-2)", whiteSpace: "pre-wrap", wordBreak: "break-word",
              }}>
                {docContent}
              </pre>
            </div>
          </div>

          {/* right: related document from other source */}
          {related && (
            <div className="v3-scroll" style={{ overflow: "auto", background: "var(--surface)" }}>
              <div style={{ padding: "12px 18px" }}>
                <h3 style={{ fontSize: 14, margin: "0 0 12px" }}>{related.file_path || related.title}</h3>
                <pre style={{
                  fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.75,
                  color: "var(--ink-2)", whiteSpace: "pre-wrap", wordBreak: "break-word",
                }}>
                  {related.content}
                </pre>
              </div>
            </div>
          )}

          {!related && (
            <div style={{ display: "none" }} />
          )}
        </div>

        <V3StatusBar
          items={[
            `${doc.chunks.length} chunks`,
            `source: ${doc.source}`,
            related ? `related: ${related.source}` : "no related doc found",
            doc.indexed_at ? `indexed ${doc.indexed_at.slice(0, 10)}` : "",
          ]}
        />
      </div>
    </div>
  );
}
