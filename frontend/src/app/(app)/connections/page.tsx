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
  // Set for notion docs (from metadata->>'notion_workspace_id'). Null for
  // github and for any pre-multi-workspace notion docs.
  workspace_id: string | null;
}

interface NotionWorkspaceConn {
  workspace_id: string;
  workspace_name: string;
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
  error?: string;
}

interface NotionGroup {
  name: string;
  source: "notion";
  workspace: string;
  workspaceId: string;
  status: SourceStatus;
  pages: number;
  chunks: number;
  lastIndexed: string;
  error?: string;
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

interface IngestJob {
  id: string;
  source: "github" | "notion";
  source_url: string;
  status: "queued" | "processing" | "embedding" | "failed";
  progress: number;
  documents_indexed: number;
  total_documents: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

function repoNameFromUrl(url: string): string {
  return url
    .replace(/^https?:\/\/github\.com\//, "")
    .replace(/\.git$/, "")
    .replace(/\/+$/, "");
}

function jobToSourceStatus(j: IngestJob): SourceStatus {
  return j.status === "failed" ? "error" : "indexing";
}

function mergeJobsIntoGroups(
  grouped: { repos: RepoGroup[]; notionSources: NotionGroup[] },
  jobs: IngestJob[],
): { repos: RepoGroup[]; notionSources: NotionGroup[] } {
  const repoNames = new Set(grouped.repos.map((r) => r.name));
  const extraRepos: RepoGroup[] = [];
  const notionInFlightByWs = new Map<string, IngestJob>();

  for (const j of jobs) {
    if (j.source === "github") {
      const name = repoNameFromUrl(j.source_url);
      if (!name || repoNames.has(name)) continue;
      repoNames.add(name);
      extraRepos.push({
        name,
        source: "github",
        branch: "main",
        status: jobToSourceStatus(j),
        files: 0,
        chunks: 0,
        lastIndexed: "—",
        progress: j.status === "failed" ? undefined : Math.max(j.progress, 0.02),
        error: j.status === "failed" ? j.error_message ?? undefined : undefined,
      });
    } else if (j.source === "notion") {
      // Track latest in-flight job per workspace_id (source_url holds it).
      const wsId = j.source_url || "default";
      const prev = notionInFlightByWs.get(wsId);
      if (!prev || j.updated_at > prev.updated_at) {
        notionInFlightByWs.set(wsId, j);
      }
    }
  }

  // Surface in-flight Notion jobs whose workspace isn't already in the
  // grouped rows (e.g. first ingest of a freshly-connected workspace
  // hasn't produced documents yet).
  const existingWorkspaceIds = new Set(
    grouped.notionSources.map((n) => n.workspaceId),
  );
  const extraNotion: NotionGroup[] = [];
  for (const [wsId, job] of notionInFlightByWs.entries()) {
    if (existingWorkspaceIds.has(wsId)) continue;
    extraNotion.push({
      name: "Notion workspace",
      source: "notion",
      workspace: wsId,
      workspaceId: wsId,
      status: jobToSourceStatus(job),
      pages: 0,
      chunks: 0,
      lastIndexed: "—",
      error:
        job.status === "failed"
          ? job.error_message ?? undefined
          : undefined,
    });
  }

  return {
    repos: [...grouped.repos, ...extraRepos],
    notionSources: [...grouped.notionSources, ...extraNotion],
  };
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
      // Group by workspace_id from doc metadata. Legacy notion docs without
      // a workspace_id (created before migration 0005) collapse to "default"
      // so they still appear under a single row instead of vanishing.
      const workspaceId = doc.workspace_id || "default";
      const existing = notionMap.get(workspaceId);
      if (existing) {
        existing.pages += 1;
        existing.chunks += doc.chunk_count;
      } else {
        notionMap.set(workspaceId, {
          name: "Notion workspace",
          source: "notion",
          workspace: workspaceId,
          workspaceId,
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
let jobsPromise: Promise<IngestJob[]> | null = null;

function fetchDocumentsPromise(): Promise<{ documents: IndexedDocument[] }> {
  if (!documentsPromise) {
    documentsPromise = apiFetch<{ documents: IndexedDocument[] }>("/api/documents/").catch(
      () => ({ documents: [] }),
    );
  }
  return documentsPromise;
}

function fetchJobsPromise(): Promise<IngestJob[]> {
  if (!jobsPromise) {
    jobsPromise = apiFetch<IngestJob[]>("/api/ingest/jobs").catch(() => []);
  }
  return jobsPromise;
}

function invalidateDocuments() {
  documentsPromise = null;
}

function invalidateJobs() {
  jobsPromise = null;
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
  // Re-applies the [CONNECTED] hardcode fix from PR #45's frontend
  // cleanup that got dropped during the squash merge — bind the tag to
  // actual state instead of always showing CONNECTED.
  connected: boolean | null;
}

function ProviderSection({
  title,
  sub,
  children,
  addLabel,
  onAdd,
  connected,
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
        {connected === true ? (
          <V3Tag tone="ok">[CONNECTED]</V3Tag>
        ) : connected === false ? (
          <V3Tag tone="err">[DISCONNECTED]</V3Tag>
        ) : (
          <V3Tag tone="acc">[…]</V3Tag>
        )}
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
          <span title={repo.error || undefined}>
            <V3StIcon st={repo.status} />
          </span>
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
  onDisconnect,
}: {
  item: NotionGroup;
  index: number;
  onReindex: () => void;
  onDisconnect: () => void;
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
        <span title={item.error || undefined}>
          <V3StIcon st={item.status} />
        </span>
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
      <td style={{ padding: "6px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
        <V3Btn size="sm" onClick={onReindex}>
          reindex
        </V3Btn>
        <span style={{ display: "inline-block", width: 6 }} />
        <V3Btn size="sm" onClick={onDisconnect}>
          disconnect
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
  const [refreshKey, setRefreshKey] = useState(0);
  const data = use(fetchDocumentsPromise());
  const jobs = use(fetchJobsPromise());
  const baseGrouped = groupDocuments(data.documents);
  const merged = mergeJobsIntoGroups(baseGrouped, jobs);

  // Refetch on window focus so users see in-flight rows + status flips
  // when they return to the tab. The Suspense boundary re-reads via the
  // refreshKey bump.
  useEffect(() => {
    function onFocus() {
      invalidateDocuments();
      invalidateJobs();
      invalidateJobs();
      setRefreshKey((k) => k + 1);
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);
  void refreshKey;

  const [extraRepos, setExtraRepos] = useState<RepoGroup[]>([]);
  const [showAddGitHub, setShowAddGitHub] = useState(false);
  const [showAddNotion, setShowAddNotion] = useState(false);
  // null = "not yet fetched"; [] = "fetched, none connected"; non-empty = list
  const [notionWorkspaces, setNotionWorkspaces] = useState<NotionWorkspaceConn[] | null>(null);
  const notionConnected = notionWorkspaces === null ? null : notionWorkspaces.length > 0;

  // Fetch connected Notion workspaces from /api/providers. The endpoint
  // returns one entry per (user, provider, workspace_id) row.
  const refreshNotionWorkspaces = useCallback(() => {
    apiFetch<{
      id: string;
      name: string;
      connected: boolean;
      workspaces?: NotionWorkspaceConn[] | null;
    }[]>("/api/providers")
      .then((providers) => {
        const notion = providers.find((p) => p.id === "notion");
        setNotionWorkspaces(notion?.workspaces ?? []);
      })
      .catch(() => setNotionWorkspaces([]));
  }, []);

  useEffect(() => {
    refreshNotionWorkspaces();
  }, [refreshNotionWorkspaces]);

  const handleConnectNotion = useCallback(() => {
    // Multi-workspace is supported — connecting adds a new row keyed on
    // (user, provider, workspace_id); existing workspaces stay intact.
    apiFetch<{ redirect_url?: string; connected?: boolean }>("/api/providers/notion/connect", {
      method: "POST",
    })
      .then((data) => {
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else if (data.connected) {
          refreshNotionWorkspaces();
        }
      })
      .catch((err) => {
        window.alert("Failed: " + (err instanceof Error ? err.message : "Notion OAuth not configured"));
      });
  }, [refreshNotionWorkspaces]);

  const handleDisconnectWorkspace = useCallback(
    (workspaceId: string, workspaceName: string) => {
      const ok = window.confirm(
        `Disconnect "${workspaceName}"?\n\n` +
          "This removes the OAuth token. Indexed pages from this workspace " +
          "will be removed on the next ingest of any workspace.",
      );
      if (!ok) return;
      apiFetch(
        `/api/providers/notion/disconnect?workspace_id=${encodeURIComponent(workspaceId)}`,
        { method: "POST" },
      )
        .then(() => {
          refreshNotionWorkspaces();
          invalidateDocuments();
          invalidateJobs();
          setRefreshKey((k) => k + 1);
        })
        .catch((err) => {
          window.alert(
            "Failed to disconnect: " + (err instanceof Error ? err.message : "unknown"),
          );
        });
    },
    [refreshNotionWorkspaces],
  );

  const repos = [...merged.repos, ...extraRepos];
  // Augment rows: for each connected workspace not yet represented by docs
  // or in-flight jobs, surface a placeholder row so the workspace is
  // visible immediately after connect (before ingest finishes).
  const workspacesInRows = new Set(merged.notionSources.map((n) => n.workspaceId));
  const placeholderNotionRows: NotionGroup[] = (notionWorkspaces ?? [])
    .filter((w) => !workspacesInRows.has(w.workspace_id))
    .map((w) => ({
      name: w.workspace_name || "Notion workspace",
      source: "notion" as const,
      workspace: w.workspace_id,
      workspaceId: w.workspace_id,
      status: "fresh" as const,
      pages: 0,
      chunks: 0,
      lastIndexed: "—",
    }));
  // Resolve workspace_name for existing rows from the providers list.
  const wsNameById = new Map(
    (notionWorkspaces ?? []).map((w) => [w.workspace_id, w.workspace_name]),
  );
  const notionSources: NotionGroup[] = [
    ...merged.notionSources.map((n) => ({
      ...n,
      name: wsNameById.get(n.workspaceId) || n.name,
    })),
    ...placeholderNotionRows,
  ];

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
      invalidateJobs();
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

  const handleIndexNotion = useCallback(
    (workspaceId: string, workspaceName: string) => {
      apiFetch<{ job_id: string }>("/api/ingest/notion", {
        method: "POST",
        body: JSON.stringify({ workspace_id: workspaceId }),
      })
        .then((data) => {
          const label = workspaceName || "notion workspace";
          registerJob(data.job_id, label, "ntn");
          invalidateDocuments();
          invalidateJobs();
          setShowAddNotion(false);
          showFeedback(data.job_id, label);
        })
        .catch((err) => {
          window.alert(`Failed: ${err instanceof Error ? err.message : "Notion not connected"}`);
        });
    },
    [showFeedback],
  );

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
              // Re-index every connected Notion workspace (one job per).
              for (const w of notionWorkspaces ?? []) {
                apiFetch<{ job_id: string }>("/api/ingest/notion", {
                  method: "POST",
                  body: JSON.stringify({ workspace_id: w.workspace_id }),
                })
                  .then((data) => {
                    registerJob(data.job_id, w.workspace_name || "notion workspace", "ntn");
                  })
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
          connected={true}
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
                    connected — no repositories indexed yet
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
          sub={
            notionConnected === true
              ? `// ${(notionWorkspaces?.length ?? 0)} workspace(s) connected`
              : notionConnected === false
              ? "// not connected"
              : "// checking…"
          }
          columnKey="page"
          columnLabel="pages"
          addLabel={notionConnected ? "connect another workspace" : "connect notion"}
          onAdd={handleConnectNotion}
          connected={notionConnected}
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
                    {notionConnected
                      ? "connected — no pages indexed yet"
                      : notionConnected === false
                      ? "not connected — click 'connect notion' below"
                      : "checking connection…"}
                  </td>
                </tr>
              ) : (
                notionSources.map((n, i) => (
                  <NotionRow
                    key={n.workspaceId}
                    item={n}
                    index={i}
                    onReindex={() => handleIndexNotion(n.workspaceId, n.name)}
                    onDisconnect={() => handleDisconnectWorkspace(n.workspaceId, n.name)}
                  />
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
