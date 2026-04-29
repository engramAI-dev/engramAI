"use client";

import React, { useState, useEffect, useCallback } from "react";
import { V3Tag, V3TitleBar, V3StatusBar, V3Input } from "@/components/engram/components";
import { apiFetch } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface DocumentItem {
  id: string;
  title: string;
  file_path: string;
  repo: string | null;
  source: string;        // "github" | "notion"
  language: string | null;
  chunk_count: number;
  freshness: number;      // 0-1
  indexed_at: string;
}

type FilterKind = "all" | "code" | "doc";

/* ------------------------------------------------------------------ */
/*  Freshness meter                                                    */
/* ------------------------------------------------------------------ */

function FreshnessMeter({ value }: { value: number }) {
  const filled = Math.round(value * 10);
  const empty = 10 - filled;
  const color =
    value > 0.7 ? "var(--phos)" : value > 0.35 ? "var(--warn)" : "var(--err)";
  return (
    <span style={{ fontSize: 10, color, letterSpacing: 0 }}>
      {"\u2588".repeat(filled)}
      {"\u2591".repeat(empty)}{" "}
      {(value * 100).toFixed(0).padStart(3, "0")}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w`;
}

function sourceLabel(src: string): string {
  if (src === "github") return "GH";
  if (src === "notion") return "NT";
  return src.slice(0, 2).toUpperCase();
}

function kindChar(src: string): { char: string; color: string } {
  return src === "github"
    ? { char: "C", color: "var(--accent)" }
    : { char: "D", color: "var(--warn)" };
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function LibraryPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKind>("all");
  const [staleOnly, setStaleOnly] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ documents: Omit<DocumentItem, "freshness">[] }>("/api/documents/");
      // Derive freshness from indexed_at: <1 day = 1.0, >30 days = 0.0
      const now = Date.now();
      const MAX_AGE = 30 * 24 * 60 * 60 * 1000; // 30 days
      setDocs(
        data.documents.map((d) => {
          const age = d.indexed_at ? now - new Date(d.indexed_at).getTime() : MAX_AGE;
          const freshness = Math.max(0, Math.min(1, 1 - age / MAX_AGE));
          return { ...d, freshness };
        }),
      );
    } catch {
      // empty — will show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = docs.filter((d) => {
    if (filter === "code" && d.source !== "github") return false;
    if (filter === "doc" && d.source !== "notion") return false;
    if (staleOnly && d.freshness > 0.7) return false;
    if (search) {
      const q = search.toLowerCase();
      if (
        !d.title.toLowerCase().includes(q) &&
        !d.file_path.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  const codeCt = docs.filter((d) => d.source === "github").length;
  const docCt = docs.filter((d) => d.source === "notion").length;
  const staleCt = docs.filter((d) => d.freshness <= 0.7).length;
  const totalChunks = docs.reduce((s, d) => s + d.chunk_count, 0);

  return (
    <div className="v3-screen v3-scan" style={{ flexDirection: "row" }}>
      <div
        className="v3-frame"
        style={{ flex: 1, border: "none", borderLeft: "1px solid var(--ink)" }}
      >
        <V3TitleBar path="engram@core:~/lib$ find . -type f" />

        {/* filter bar */}
        <div
          style={{
            padding: "8px 14px",
            display: "flex",
            alignItems: "center",
            gap: 6,
            borderBottom: "1px solid var(--ink)",
            background: "var(--surface)",
          }}
        >
          <button onClick={() => { setFilter("all"); setStaleOnly(false); }} style={{ all: "unset", cursor: "pointer" }}>
            <V3Tag tone={filter === "all" ? "fill" : undefined}>all {docs.length}</V3Tag>
          </button>
          <button onClick={() => setFilter("code")} style={{ all: "unset", cursor: "pointer" }}>
            <V3Tag tone={filter === "code" ? "fill" : undefined}>code {codeCt}</V3Tag>
          </button>
          <button onClick={() => setFilter("doc")} style={{ all: "unset", cursor: "pointer" }}>
            <V3Tag tone={filter === "doc" ? "fill" : undefined}>doc {docCt}</V3Tag>
          </button>
          <button onClick={() => setStaleOnly(!staleOnly)} style={{ all: "unset", cursor: "pointer" }}>
            <V3Tag tone={staleOnly ? "warn" : undefined}>stale {staleCt}</V3Tag>
          </button>
          <span style={{ flex: 1 }} />
          <span style={{ color: "var(--accent)" }}>/</span>
          <V3Input
            placeholder="grep across files & pages"
            style={{ width: 260, height: 22 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* table */}
        <div className="v3-scroll" style={{ flex: 1, overflow: "auto", overflowX: "auto" }}>
          {loading ? (
            <div style={{ padding: 24, color: "var(--ink-3)", fontSize: 12 }}>
              loading index...
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 24, color: "var(--ink-4)", fontSize: 12 }}>
              {docs.length === 0
                ? "no indexed documents. connect a source to begin."
                : "no documents match current filters."}
            </div>
          ) : (
            <table
              style={{
                minWidth: 700,
                width: "100%",
                borderCollapse: "collapse",
                fontFamily: "var(--font-mono)",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--ink)",
                    background: "var(--surface)",
                    position: "sticky",
                    top: 0,
                  }}
                >
                  {["k", "title", "repo", "src", "chk", "fresh", "at"].map(
                    (h, i) => (
                      <th
                        key={i}
                        className="v3-cap"
                        style={{ textAlign: "left", padding: "6px 10px", fontSize: 10 }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, i) => {
                  const kc = kindChar(r.source);
                  const isStale = r.freshness <= 0.35;
                  return (
                    <tr
                      key={r.id}
                      style={{ borderBottom: "1px dashed var(--line-2)" }}
                    >
                      <td
                        style={{
                          padding: "5px 10px",
                          fontSize: 11,
                          color: kc.color,
                        }}
                      >
                        {kc.char}
                      </td>
                      <td style={{ padding: "5px 10px", fontSize: 12, color: "var(--ink)" }}>
                        <div>{r.title}</div>
                        {r.file_path && r.file_path !== r.title && (
                          <div style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 1 }}>{r.file_path}</div>
                        )}
                        {isStale && (
                          <span style={{ marginLeft: 4 }}>
                            <V3Tag tone="warn">STALE</V3Tag>
                          </span>
                        )}
                      </td>
                      <td
                        style={{
                          padding: "5px 10px",
                          fontSize: 10,
                          color: "var(--accent)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {r.repo || "\u2014"}
                      </td>
                      <td
                        style={{
                          padding: "5px 10px",
                          fontSize: 11,
                          color: "var(--ink-3)",
                        }}
                      >
                        {sourceLabel(r.source)}
                      </td>
                      <td
                        style={{
                          padding: "5px 10px",
                          fontSize: 12,
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {r.chunk_count}
                      </td>
                      <td style={{ padding: "5px 10px" }}>
                        <FreshnessMeter value={r.freshness} />
                      </td>
                      <td
                        style={{
                          padding: "5px 10px",
                          fontSize: 11,
                          color: "var(--ink-4)",
                        }}
                      >
                        {relativeTime(r.indexed_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <V3StatusBar
          items={[
            `${docs.length} entries`,
            `${staleCt} stale`,
            "sorted by age desc",
            `${totalChunks.toLocaleString()} chunks`,
            "engine pgvector-hnsw",
          ]}
        />
      </div>
    </div>
  );
}
