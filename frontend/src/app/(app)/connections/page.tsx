"use client";

/**
 * Connections page — v3 "Datasheet / CRT" terminal aesthetic.
 * Manage GitHub repos and Notion workspaces with tabular display.
 */

import { useCallback, useEffect, use, useState, Suspense } from "react";
import { apiFetch } from "@/lib/api";
import { registerJob } from "@/app/(app)/jobs/page";
import { TopBar } from "@/components/engram/top-bar";
import {
  V3Tag,
  V3Btn,
  V3StatusBar,
  V3Input,
} from "@/components/engram/components";

// -------------------------------------------------------------------
// Types
// -------------------------------------------------------------------

type SourceStatus = "fresh" | "stale" | "indexing" | "error";

interface IndexedDocument {
  id: string;
  title: string;
  source: "github" | "notion";
  repo: string | null;
  file_path: string | null;
  url: string;
  chunk_count: number;
  indexed_at: string | null;
}

interface RepoGroup {
  name: string;
  source: "github";
  branch: string;
  status: SourceStatus;
  files: number;
  chunks: number;
  lastIndexed: string;
  progress?: number;
}

interface NotionGroup {
  name: string;
  source: "notion";
  workspace: string;
  status: SourceStatus;
  pages: number;
  chunks: number;
  lastIndexed: string;
}

// -------------------------------------------------------------------
// Status icon — v3 bracket tag style
// -------------------------------------------------------------------

function V3StIcon({ st }: { st: SourceStatus }) {
  if (st === "fresh") return <V3Tag tone="ok">[OK]</V3Tag>;
  if (st === "stale") return <V3Tag tone="warn">[STALE]</V3Tag>;
  if (st === "indexing") return <V3Tag tone="acc">[IDX]</V3Tag>;
  return <V3Tag tone="err">[ERR]</V3Tag>;
}

// -------------------------------------------------------------------
// Utility
// -------------------------------------------------------------------

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w`;
}

function groupDocuments(documents: IndexedDocument[]): {
  repos: RepoGroup[];
  notionSources: NotionGroup[];
} {
  const repoMap = new Map<string, RepoGroup>();
  const notionMap = new Map<string, NotionGroup>();

  for (const doc of documents) {
    if (doc.source === "github" && doc.repo) {
      const existing = repoMap.get(doc.repo);
      if (existing) {
        existing.files += 1;
        existing.chunks += doc.chunk_count;
      } else {
        repoMap.set(doc.repo, {
          name: doc.repo,
          source: "github",
          branch: "main",
          status: "fresh",
          files: 1,
          chunks: doc.chunk_count,
          lastIndexed: doc.indexed_at
            ? formatRelativeTime(doc.indexed_at)
            : "\u2014",
        });
      }
    } else if (doc.source === "notion") {
      const workspace = doc.repo || "default";
      const existing = notionMap.get(workspace);
      if (existing) {
        existing.pages += 1;
        existing.chunks += doc.chunk_count;
      } else {
        notionMap.set(workspace, {
          name: "Notion workspace",
          source: "notion",
          workspace,
          status: "fresh",
          pages: 1,
          chunks: doc.chunk_count,
          lastIndexed: doc.indexed_at
            ? formatRelativeTime(doc.indexed_at)
            : "\u2014",
        });
      }
    }
  }

  return {
    repos: Array.from(repoMap.values()),
    notionSources: Array.from(notionMap.values()),
  };
}

// -------------------------------------------------------------------
// Data fetcher (uses React 19 `use()` to avoid setState in useEffect)
// -------------------------------------------------------------------

let documentsPromise: Promise<{ documents: IndexedDocument[] }> | null = null;

function fetchDocumentsPromise(): Promise<{ documents: IndexedDocument[] }> {
  if (!documentsPromise) {
    documentsPromise = apiFetch<{ documents: IndexedDocument[] }>("/api/documents/").catch(
      () => ({ documents: [] }),
    );
  }
  return documentsPromise;
}

function invalidateDocuments() {
  documentsPromise = null;
}

// -------------------------------------------------------------------
// Provider section with table
// -------------------------------------------------------------------

interface ProviderSectionProps {
  id: string;
  title: string;
  sub: string;
  columnKey: "repo" | "page";
  columnLabel: string;
  children: React.ReactNode;
  addLabel: string;
  onAdd?: () => void;
}

function ProviderSection({
  title,
  sub,
  children,
  addLabel,
  onAdd,
}: ProviderSectionProps) {
  return (
    <section style={{ borderBottom: "1px solid var(--ink)" }}>
      <div
        style={{
          padding: "10px 22px",
          borderBottom: "1px solid var(--line, var(--ink-4))",
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: "var(--surface)",
        }}
      >
        <span
          style={{
            color: "var(--accent)",
            fontSize: 13,
            fontWeight: 600,
            fontFamily: "var(--font-mono)",
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10.5,
            color: "var(--ink-4)",
          }}
        >
          {sub}
        </span>
        <span style={{ flex: 1 }} />
        <V3Tag tone="ok">[CONNECTED]</V3Tag>
      </div>
      {children}
      <div
        onClick={onAdd}
        style={{
          padding: "8px 22px",
          color: "var(--accent)",
          fontSize: 11,
          cursor: "pointer",
          background: "var(--surface)",
          fontFamily: "var(--font-mono)",
          borderTop: "1px dotted var(--line, var(--ink-4))",
        }}
      >
        + {addLabel}
      </div>
    </section>
  );
}

// -------------------------------------------------------------------
// Table header
// -------------------------------------------------------------------

function TableHeader({ isRepo }: { isRepo: boolean }) {
  const cols = ["#", "name", isRepo ? "branch" : "workspace", isRepo ? "files" : "pages", "chunks", "status", "last indexed", ""];
  return (
    <tr
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--ink)",
      }}
    >
      {cols.map((h, i) => (
        <th
          key={i}
          style={{
            textAlign: "left",
            padding: "6px 10px",
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--ink-3)",
            fontWeight: 500,
          }}
        >
          {h}
        </th>
      ))}
    </tr>
  );
}

// -------------------------------------------------------------------
// GitHub row
// -------------------------------------------------------------------

function GitHubRow({
  repo,
  index,
  onReindex,
}: {
  repo: RepoGroup;
  index: number;
  onReindex: (name: string) => void;
}) {
  return (
    <tr style={{ borderBottom: "1px dashed var(--line, var(--ink-4))" }}>
      <td
        style={{
          padding: "6px 10px",
          color: "var(--ink-4)",
          fontSize: 11,
          fontVariantNumeric: "tabular-nums",
          fontFamily: "var(--font-mono)",
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          color: "var(--ink)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {repo.name}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 11,
          color: "var(--ink-3)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {repo.branch}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          fontVariantNumeric: "tabular-nums",
          fontFamily: "var(--font-mono)",
        }}
      >
        {repo.files.toLocaleString()}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          fontVariantNumeric: "tabular-nums",
          color: "var(--ink-3)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {repo.chunks.toLocaleString()}
      </td>
      <td style={{ padding: "6px 10px" }}>
        {repo.status === "indexing" && repo.progress != null ? (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <V3StIcon st="indexing" />
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--ink-3)",
              }}
            >
              {"\u2588".repeat(Math.round((repo.progress) * 10))}
              {"\u2591".repeat(10 - Math.round((repo.progress) * 10))}{" "}
              {Math.round((repo.progress) * 100)}%
            </span>
          </div>
        ) : (
          <V3StIcon st={repo.status} />
        )}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 11,
          color: "var(--ink-4)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {repo.lastIndexed}
      </td>
      <td style={{ padding: "6px 10px", textAlign: "right" }}>
        <V3Btn size="sm" onClick={() => onReindex(repo.name)}>
          reindex
        </V3Btn>
      </td>
    </tr>
  );
}

// -------------------------------------------------------------------
// Notion row
// -------------------------------------------------------------------

function NotionRow({
  item,
  index,
  onReindex,
}: {
  item: NotionGroup;
  index: number;
  onReindex: () => void;
}) {
  return (
    <tr style={{ borderBottom: "1px dashed var(--line, var(--ink-4))" }}>
      <td
        style={{
          padding: "6px 10px",
          color: "var(--ink-4)",
          fontSize: 11,
          fontVariantNumeric: "tabular-nums",
          fontFamily: "var(--font-mono)",
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          color: "var(--ink)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {item.name}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 11,
          color: "var(--ink-3)",
          fontFamily: "var(--font-mono)",
        }}
      >
        primary
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          fontVariantNumeric: "tabular-nums",
          fontFamily: "var(--font-mono)",
        }}
      >
        {item.pages.toLocaleString()}
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 12,
          fontVariantNumeric: "tabular-nums",
          color: "var(--ink-3)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {item.chunks.toLocaleString()}
      </td>
      <td style={{ padding: "6px 10px" }}>
        <V3StIcon st={item.status} />
      </td>
      <td
        style={{
          padding: "6px 10px",
          fontSize: 11,
          color: "var(--ink-4)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {item.lastIndexed}
      </td>
      <td style={{ padding: "6px 10px", textAlign: "right" }}>
        <V3Btn size="sm" onClick={onReindex}>
          reindex
        </V3Btn>
      </td>
    </tr>
  );
}

// -------------------------------------------------------------------
// Add repo form
// -------------------------------------------------------------------

function AddRepoForm({
  onAdd,
  onCancel,
}: {
  onAdd: (url: string) => void;
  onCancel: () => void;
}) {
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);

  const handleAdd = useCallback(() => {
    const trimmed = url.trim();
    if (!trimmed || adding) return;
    setAdding(true);
    try {
      onAdd(trimmed);
      setUrl("");
    } finally {
      setAdding(false);
    }
  }, [url, adding, onAdd]);

  return (
    <section style={{ borderBottom: "1px solid var(--ink)", padding: "14px 22px" }}>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--ink-3)",
          marginBottom: 10,
        }}
      >
        add repository
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <V3Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/org/repo"
          style={{ flex: 1 }}
        />
        <V3Btn
          variant="acc"
          size="sm"
          onClick={handleAdd}
          disabled={!url.trim() || adding}
        >
          add & index
        </V3Btn>
        <V3Btn size="sm" onClick={onCancel}>
          cancel
        </V3Btn>
      </div>
    </section>
  );
}

// -------------------------------------------------------------------
// Inner content (suspense boundary for `use()`)
// -------------------------------------------------------------------

function ConnectionsContent() {
  const data = use(fetchDocumentsPromise());
  const grouped = groupDocuments(data.documents);

  const [extraRepos, setExtraRepos] = useState<RepoGroup[]>([]);
  const [showAddGitHub, setShowAddGitHub] = useState(false);
  const [showAddNotion, setShowAddNotion] = useState(false);
  const [notionConnected, setNotionConnected] = useState<boolean | null>(null);
  const [notionWorkspaceName, setNotionWorkspaceName] = useState("Notion workspace");

  // Check if Notion is connected via OAuth
  useEffect(() => {
    apiFetch<{ id: string; name: string; connected: boolean; metadata: Record<string, string> }[]>("/api/providers")
      .then((providers) => {
        const notion = providers.find((p) => p.id === "notion");
        setNotionConnected(notion?.connected ?? false);
        if (notion?.metadata?.workspace_name) {
          setNotionWorkspaceName(notion.metadata.workspace_name);
        }
      })
      .catch(() => setNotionConnected(false));
  }, []);

  const handleConnectNotion = useCallback(() => {
    apiFetch<{ redirect_url?: string; connected?: boolean }>("/api/providers/notion/connect", {
      method: "POST",
    })
      .then((data) => {
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else if (data.connected) {
          setNotionConnected(true);
        }
      })
      .catch((err) => {
        window.alert("Failed: " + (err instanceof Error ? err.message : "Notion OAuth not configured"));
      });
  }, []);

  const repos = [...grouped.repos, ...extraRepos];
  const notionSources = grouped.notionSources.map((n) => ({
    ...n,
    name: notionWorkspaceName,
  }));

  const totalSources = repos.length + notionSources.length;
  const totalChunks =
    repos.reduce((s, r) => s + r.chunks, 0) +
    notionSources.reduce((s, n) => s + n.chunks, 0);

  const handleAddRepo = useCallback(
    (url: string) => {
      apiFetch<{ job_id: string }>("/api/ingest/github", {
        method: "POST",
        body: JSON.stringify({ repo_url: url }),
      })
        .then((data) => {
          const repoName = url.replace("https://github.com/", "");
          registerJob(data.job_id, repoName, "git");
        })
        .catch(() => {});

      setExtraRepos((prev) => [
        ...prev,
        {
          name: url.replace("https://github.com/", ""),
          source: "github",
          branch: "main",
          status: "indexing",
          files: 0,
          chunks: 0,
          lastIndexed: "now",
          progress: 0,
        },
      ]);
      setShowAddGitHub(false);
      invalidateDocuments();
    },
    [],
  );

  const [reindexFeedback, setReindexFeedback] = useState<{ msg: string; jobId: string } | null>(null);

  const showFeedback = useCallback((jobId: string, title: string) => {
    setReindexFeedback({ msg: `job ${jobId.slice(0, 8)} started for ${title}`, jobId });
    setTimeout(() => setReindexFeedback(null), 8000);
  }, []);

  const handleReindex = useCallback((repoName: string) => {
    apiFetch<{ job_id: string }>("/api/ingest/github", {
      method: "POST",
      body: JSON.stringify({ repo_url: `https://github.com/${repoName}` }),
    })
      .then((data) => {
        registerJob(data.job_id, repoName, "git");
        showFeedback(data.job_id, repoName);
      })
      .catch(() => {});
  }, [showFeedback]);

  const handleReindexAndNavigate = useCallback((repoName: string) => {
    apiFetch<{ job_id: string }>("/api/ingest/github", {
      method: "POST",
      body: JSON.stringify({ repo_url: `https://github.com/${repoName}` }),
    })
      .then((data) => {
        registerJob(data.job_id, repoName, "git");
        window.open(`/jobs?job=${data.job_id}`, "_self");
      })
      .catch(() => {});
  }, []);

  const handleIndexNotion = useCallback(() => {
    apiFetch<{ job_id: string }>("/api/ingest/notion", {
      method: "POST",
      body: JSON.stringify({ workspace_id: "default" }),
    })
      .then((data) => {
        registerJob(data.job_id, "notion workspace", "ntn");
        invalidateDocuments();
        setShowAddNotion(false);
        showFeedback(data.job_id, "notion workspace");
      })
      .catch((err) => {
        window.alert(`Failed: ${err instanceof Error ? err.message : "Notion not connected"}`);
      });
  }, [showFeedback]);

  return (
    <>
      <TopBar
        path="engram@core:~/sources$ ls -la"
        right={
          <button
            onClick={() => {
              // Re-index all GitHub repos
              for (const repo of repos) {
                handleReindex(repo.name);
              }
              // Re-index Notion
              if (notionSources.length > 0) {
                apiFetch<{ job_id: string }>("/api/ingest/notion", {
                  method: "POST",
                  body: JSON.stringify({ workspace_id: "default" }),
                })
                  .then((data) => { registerJob(data.job_id, "notion workspace", "ntn"); })
                  .catch(() => {});
              }
            }}
            style={{
              background: "transparent",
              border: "1px solid var(--bg)",
              color: "var(--bg)",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              padding: "2px 8px",
              cursor: "pointer",
              letterSpacing: "0.04em",
            }}
          >
            {"[ reindex --all ]"}
          </button>
        }
      />

      {reindexFeedback !== null && (
        <div style={{
          padding: "8px 22px",
          background: "var(--accent-soft)",
          borderBottom: "1px solid var(--accent)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}>
          <span>{"●"}</span>
          <span>{reindexFeedback.msg}</span>
          <span style={{ flex: 1 }} />
          <button
            onClick={() => window.open(`/jobs?job=${reindexFeedback.jobId}`, "_self")}
            style={{
              background: "transparent",
              border: "1px solid var(--accent)",
              color: "var(--accent)",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            {"view jobs \u2192"}
          </button>
        </div>
      )}
      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Stats header */}
        <div
          style={{
            padding: "10px 22px",
            borderBottom: "1px solid var(--ink)",
            display: "flex",
            gap: 16,
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--ink-3)",
            background: "var(--surface)",
          }}
        >
          <span>
            <span style={{ color: "var(--ink)", fontWeight: 600 }}>{totalSources}</span> sources
          </span>
          <span>
            <span style={{ color: "var(--ink)", fontWeight: 600 }}>{totalChunks.toLocaleString()}</span> chunks
          </span>
          <span>
            <span style={{ color: "var(--ink)", fontWeight: 600 }}>{repos.length}</span> github
          </span>
          <span>
            <span style={{ color: "var(--ink)", fontWeight: 600 }}>{notionSources.length}</span> notion
          </span>
        </div>

        {/* Add form */}
        {showAddGitHub && (
          <AddRepoForm onAdd={handleAddRepo} onCancel={() => setShowAddGitHub(false)} />
        )}

        {/* GitHub provider */}
        <ProviderSection
          id="gh"
          title="github.providers"
          sub="// oauth · token-in-url cloning · code = source of truth"
          columnKey="repo"
          columnLabel="docs"
          addLabel="add repository"
          onAdd={() => setShowAddGitHub(true)}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontFamily: "var(--font-mono)",
            }}
          >
            <thead>
              <TableHeader isRepo />
            </thead>
            <tbody>
              {repos.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    style={{
                      padding: "32px 22px",
                      textAlign: "center",
                      color: "var(--ink-4)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                    }}
                  >
                    no repositories connected yet
                  </td>
                </tr>
              ) : (
                repos.map((r, i) => (
                  <GitHubRow key={r.name} repo={r} index={i} onReindex={handleReindex} />
                ))
              )}
            </tbody>
          </table>
        </ProviderSection>

        {/* Notion provider */}
        <ProviderSection
          id="no"
          title="notion.providers"
          sub={notionConnected ? "// connected" : "// not connected"}
          columnKey="page"
          columnLabel="pages"
          addLabel={notionConnected ? "connect another workspace" : "connect notion"}
          onAdd={handleConnectNotion}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontFamily: "var(--font-mono)",
            }}
          >
            <thead>
              <TableHeader isRepo={false} />
            </thead>
            <tbody>
              {notionSources.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    style={{
                      padding: "32px 22px",
                      textAlign: "center",
                      color: "var(--ink-4)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                    }}
                  >
                    no workspaces connected yet
                  </td>
                </tr>
              ) : (
                notionSources.map((n, i) => (
                  <NotionRow key={n.workspace} item={n} index={i} onReindex={handleIndexNotion} />
                ))
              )}
            </tbody>
          </table>
        </ProviderSection>
      </div>

      <V3StatusBar
        items={[
          `${totalSources} sources`,
          `${totalChunks.toLocaleString()} chunks`,
          `${repos.length} github`,
          `${notionSources.length} notion`,
        ]}
      />
    </>
  );
}

// -------------------------------------------------------------------
// Loading fallback
// -------------------------------------------------------------------

function ConnectionsLoading() {
  return (
    <>
      <TopBar path="engram@core:~/sources$ ls -la" />
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--ink-3)",
        }}
      >
        loading sources...
      </div>
      <V3StatusBar items={["loading\u2026"]} />
    </>
  );
}

// -------------------------------------------------------------------
// Page
// -------------------------------------------------------------------

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<ConnectionsLoading />}>
      <ConnectionsContent />
    </Suspense>
  );
}
