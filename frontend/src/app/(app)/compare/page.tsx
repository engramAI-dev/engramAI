"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { V3Tag, V3TitleBar, V3StatusBar, V3Hr } from "@/components/engram/components";

interface DocItem {
  id: string;
  title: string;
  source: string;
  repo: string | null;
  file_path: string | null;
}

export default function CompareIndexPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const PAGE_SIZE = 30;
  const [ghVisible, setGhVisible] = useState(PAGE_SIZE);
  const [ntVisible, setNtVisible] = useState(PAGE_SIZE);

  const load = useCallback(() => {
    apiFetch<{ documents: DocItem[] }>("/api/documents/?limit=500")
      .then((data) => setDocs(data.documents))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const q = search.toLowerCase();
  const githubDocs = docs.filter((d) => d.source === "github" && (!q || (d.file_path || d.title).toLowerCase().includes(q)));
  const allGithubCount = docs.filter((d) => d.source === "github").length;
  const notionDocs = docs.filter((d) => d.source === "notion" && (!q || d.title.toLowerCase().includes(q)));

  return (
    <div className="v3-screen v3-scan">
      <V3TitleBar path="engram@core:~/diff$ ls" />

      <div className="v3-scroll" style={{ flex: 1, overflow: "auto" }}>
        <div style={{ maxWidth: 640, padding: "24px 28px" }}>
          <span className="v3-cap">compare doc {"<->"} code</span>
          <V3Hr />

          {loading ? (
            <div style={{ color: "var(--ink-4)", fontSize: 11 }}>loading documents...</div>
          ) : docs.length === 0 ? (
            <div style={{ color: "var(--ink-4)", fontSize: 11 }}>
              {`// no documents indexed yet. index a repo and notion workspace first.`}
            </div>
          ) : (
            <>
              <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 16 }}>
                {`// select a document to compare against related content from the other source`}
              </div>
              <div style={{ marginBottom: 16 }}>
                <input
                  className="v3-input"
                  placeholder="filter files..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setGhVisible(PAGE_SIZE); setNtVisible(PAGE_SIZE); }}
                  style={{ width: 300 }}
                />
                <span style={{ marginLeft: 8, fontSize: 10, color: "var(--ink-4)" }}>
                  {githubDocs.length + notionDocs.length} of {docs.length} files
                </span>
              </div>

              {notionDocs.length > 0 && (
                <>
                  <span className="v3-cap" style={{ marginTop: 16 }}>notion pages ({notionDocs.length})</span>
                  <div style={{ marginTop: 8 }}>
                    {notionDocs.slice(0, ntVisible).map((d) => (
                      <div
                        key={d.id}
                        onClick={() => router.push(`/compare/${d.id}`)}
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          padding: "6px 0", borderBottom: "1px dashed var(--line)",
                          cursor: "pointer", fontSize: 12,
                        }}
                      >
                        <V3Tag tone="warn">NTN</V3Tag>
                        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {d.title}
                        </span>
                        <span style={{ color: "var(--ink-4)", fontSize: 10 }}>{d.id.slice(0, 8)}</span>
                      </div>
                    ))}
                    {notionDocs.length > ntVisible && (
                      <button
                        onClick={() => setNtVisible((v) => v + PAGE_SIZE)}
                        style={{
                          display: "block", width: "100%", padding: "8px 0",
                          background: "transparent", border: "none", cursor: "pointer",
                          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)",
                        }}
                      >
                        {"[ load more ]"} ({notionDocs.length - ntVisible} remaining)
                      </button>
                    )}
                  </div>
                </>
              )}

              {githubDocs.length > 0 && (
                <>
                  <span className="v3-cap" style={{ marginTop: 20, display: "block" }}>github files ({githubDocs.length})</span>
                  <div style={{ marginTop: 8 }}>
                    {githubDocs.slice(0, ghVisible).map((d) => (
                      <div
                        key={d.id}
                        onClick={() => router.push(`/compare/${d.id}`)}
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          padding: "6px 0", borderBottom: "1px dashed var(--line)",
                          cursor: "pointer", fontSize: 12,
                        }}
                      >
                        <V3Tag tone="ok">GIT</V3Tag>
                        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {d.file_path || d.title}
                        </span>
                        <span style={{ color: "var(--ink-4)", fontSize: 10 }}>{d.repo}</span>
                      </div>
                    ))}
                    {githubDocs.length > ghVisible && (
                      <button
                        onClick={() => setGhVisible((v) => v + PAGE_SIZE)}
                        style={{
                          display: "block", width: "100%", padding: "8px 0",
                          background: "transparent", border: "none", cursor: "pointer",
                          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)",
                        }}
                      >
                        {"[ load more ]"} ({githubDocs.length - ghVisible} remaining)
                      </button>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>

      <V3StatusBar items={[`${notionDocs.length} notion`, `${githubDocs.length} github`, `${docs.length} total`]} />
    </div>
  );
}
