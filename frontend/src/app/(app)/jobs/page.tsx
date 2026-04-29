"use client";

import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { V3Tag, V3TitleBar, V3StatusBar } from "@/components/engram/components";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ApiJob {
  job_id: string;
  status: string; // queued | processing | embedding | complete | failed
  progress: number;
  documents_indexed: number;
  total_documents: number | null;
  error: string | null;
}

interface Job {
  id: string;
  title: string;
  src: "git" | "ntn";
  station: "queue" | "clone" | "chunk" | "embed" | "done" | "fail";
  progress: number;
  documents_indexed: number;
  total_documents: number | null;
  error: string | null;
}

const STORAGE_KEY = "engram_job_ids";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function loadJobIds(): { id: string; title: string; src: "git" | "ntn" }[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/** Call this from other pages (connections, onboarding) after POST /api/ingest */
export function registerJob(id: string, title: string, src: "git" | "ntn") {
  const existing = loadJobIds();
  if (existing.some((j) => j.id === id)) return;
  // Keep last 20 jobs
  const updated = [{ id, title, src }, ...existing].slice(0, 20);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
}

function mapStatus(status: string): Job["station"] {
  switch (status) {
    case "queued": return "queue";
    case "processing": return "chunk";
    case "embedding": return "embed";
    case "complete": return "done";
    case "failed": return "fail";
    default: return "queue";
  }
}

/* ------------------------------------------------------------------ */
/*  Pipeline component                                                 */
/* ------------------------------------------------------------------ */

const STATIONS = ["queue", "clone", "chunk", "embed", "done"] as const;

function stationIcon(station: string, current: string): string {
  const ci = STATIONS.indexOf(current as typeof STATIONS[number]);
  const si = STATIONS.indexOf(station as typeof STATIONS[number]);
  if (current === "fail") return si === 0 ? "\u2713" : "\u2718";
  if (si < ci) return "\u2713";
  if (si === ci) return "\u2588";
  return "\u2591";
}

function Pipeline({ current }: { current: string }) {
  return (
    <pre style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.65, color: "var(--ink-2)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {STATIONS.map((s, i) => {
        const icon = stationIcon(s, current);
        const ci = STATIONS.indexOf(current as typeof STATIONS[number]);
        const isActive = i === ci;
        const color = current === "fail" && i > 0 ? "var(--err)" : isActive ? "var(--accent)" : i < ci ? "var(--phos)" : "var(--ink-4)";
        return (
          <React.Fragment key={s}>
            <span style={{ color }}>[{icon} {s}]</span>
            {i < STATIONS.length - 1 && <span style={{ color: "var(--ink-4)" }}>{"\u2500\u2500"}</span>}
          </React.Fragment>
        );
      })}
    </pre>
  );
}

function stationTag(station: string, isSelected: boolean): React.ReactNode {
  if (station === "done") return <V3Tag tone="ok">DONE</V3Tag>;
  if (station === "fail") return <V3Tag tone="err">FAIL</V3Tag>;
  return <V3Tag tone={isSelected ? "acc" : "warn"}>{station.toUpperCase()}</V3Tag>;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

function JobsPageInner() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const params = useSearchParams();
  const targetJobId = params.get("job");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = useCallback(async () => {
    const stored = loadJobIds();
    if (stored.length === 0) return;

    const results = await Promise.allSettled(
      stored.map((j) =>
        apiFetch<ApiJob>(`/api/ingest/status/${j.id}`)
          .then((data) => ({
            id: j.id,
            title: j.title,
            src: j.src,
            station: mapStatus(data.status),
            progress: data.progress,
            documents_indexed: data.documents_indexed,
            total_documents: data.total_documents,
            error: data.error,
          }))
          .catch(() => ({
            id: j.id,
            title: j.title,
            src: j.src,
            station: "fail" as const,
            progress: 0,
            documents_indexed: 0,
            total_documents: null,
            error: "Failed to fetch status",
          }))
      )
    );

    const updated: Job[] = results
      .filter((r): r is PromiseFulfilledResult<Job> => r.status === "fulfilled")
      .map((r) => r.value);

    setJobs(updated);
    // Auto-select job from ?job= query param
    if (targetJobId) {
      const idx = updated.findIndex((j) => j.id === targetJobId);
      if (idx >= 0) setSelectedIdx(idx);
    }
  }, []);

  // Initial fetch + poll every 5s
  useEffect(() => {
    const poll = () => { fetchJobs(); };
    poll();
    pollRef.current = setInterval(poll, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchJobs]);

  const selected = jobs[selectedIdx] ?? null;
  const activeJobs = jobs.filter((j) => j.station !== "done" && j.station !== "fail");

  if (jobs.length === 0) {
    return (
      <div className="v3-screen v3-scan">
        <V3TitleBar path="engram@core:~/jobs$ tail -f worker.log" />
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ textAlign: "center", color: "var(--ink-4)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
            <div style={{ marginBottom: 8 }}>no jobs yet</div>
            <div style={{ fontSize: 11 }}>{`// index a repo or notion workspace to see jobs here`}</div>
          </div>
        </div>
        <V3StatusBar items={["worker idle", "queue empty"]} />
      </div>
    );
  }

  const pct = selected ? Math.round(selected.progress * 100) : 0;

  return (
    <div className="v3-screen v3-scan" style={{ flexDirection: "row" }}>
      <div className="v3-frame" style={{ flex: 1, border: "none", borderLeft: "1px solid var(--ink)" }}>
        <V3TitleBar path="engram@core:~/jobs$ tail -f worker.log" />

        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(200px, 260px) 1fr", overflow: "hidden", minHeight: 0 }}>
          {/* left: job list */}
          <aside className="v3-scroll" style={{ overflow: "auto", borderRight: "1px solid var(--ink)", background: "var(--surface)" }}>
            <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
              <span className="v3-cap">queue · {activeJobs.length} active</span>
            </div>

            {jobs.map((j, i) => {
              const on = i === selectedIdx;
              return (
                <div
                  key={j.id}
                  onClick={() => setSelectedIdx(i)}
                  style={{
                    padding: "8px 12px",
                    borderBottom: "1px solid var(--line)",
                    background: on ? "var(--ink)" : "transparent",
                    color: on ? "var(--bg)" : "var(--ink)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                    <span style={{ color: on ? "var(--accent)" : "var(--ink-4)" }}>{j.src}</span>
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: on ? "var(--bg)" : "var(--ink)" }}>
                      {j.title}
                    </span>
                    {stationTag(j.station, on)}
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, marginTop: 4, color: on ? "var(--ink-5)" : "var(--ink-3)" }}>
                    {"\u2588".repeat(Math.round(j.progress * 20))}
                    {"\u2591".repeat(20 - Math.round(j.progress * 20))}{" "}
                    {(j.progress * 100).toFixed(0)}%
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2, fontSize: 10, color: on ? "var(--ink-5)" : "var(--ink-4)" }}>
                    <span>{j.id.slice(0, 8)}</span>
                    <span>
                      {j.station === "done" ? "complete" : j.station === "fail" ? "failed" : "running"}
                    </span>
                  </div>
                </div>
              );
            })}
          </aside>

          {/* right: selected job detail */}
          {selected ? (
            <div className="v3-scroll" style={{ overflow: "auto" }}>
              <div style={{ padding: "16px 22px", borderBottom: "1px solid var(--ink)" }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
                  <span className="v3-bignum" style={{ color: "var(--accent)" }}>{pct}</span>
                  <span style={{ fontSize: 18, color: "var(--ink-3)" }}>%</span>
                  <span style={{ flex: 1 }} />
                  {stationTag(selected.station, true)}
                  {selected.total_documents && (
                    <V3Tag>{selected.documents_indexed}/{selected.total_documents} files</V3Tag>
                  )}
                </div>

                <Pipeline current={selected.station} />

                <pre style={{ margin: "12px 0 0", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.65, color: "var(--ink-2)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
{`job:    ${selected.id}
title:  ${selected.title}
source: ${selected.src === "git" ? "github" : "notion"}
status: ${selected.station}
${"─".repeat(50)}
progress:  ${pct}%
indexed:   ${selected.documents_indexed} documents
total:     ${selected.total_documents ?? "unknown"}`}
{selected.error ? `\nerror:     ${selected.error}` : ""}
                </pre>

                {/* Cancel button for active jobs */}
                {selected.station !== "done" && selected.station !== "fail" && (
                  <div style={{ marginTop: 16 }}>
                    <button
                      className="v3-btn"
                      style={{ borderColor: "var(--err)", color: "var(--err)" }}
                      onClick={() => {
                        apiFetch(`/api/ingest/cancel/${selected.id}`, { method: "POST" })
                          .then(() => fetchJobs())
                          .catch(() => {});
                      }}
                    >
                      cancel job
                    </button>
                  </div>
                )}

                {/* Re-run button for failed jobs */}
                {selected.station === "fail" && (
                  <div style={{ marginTop: 16 }}>
                    <button
                      className="v3-btn"
                      data-variant="acc"
                      onClick={() => {
                        const endpoint = selected.src === "git" ? "/api/ingest/github" : "/api/ingest/notion";
                        const body = selected.src === "git"
                          ? { repo_url: `https://github.com/${selected.title}` }
                          : { workspace_id: "default" };
                        apiFetch<{ job_id: string }>(endpoint, {
                          method: "POST",
                          body: JSON.stringify(body),
                        })
                          .then((data) => {
                            registerJob(data.job_id, selected.title, selected.src);
                            fetchJobs();
                          })
                          .catch(() => {});
                      }}
                    >
                      re-run job
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ink-4)" }}>
              select a job
            </div>
          )}
        </div>

        <V3StatusBar
          items={[
            `${activeJobs.length} active`,
            `${jobs.filter((j) => j.station === "done").length} complete`,
            `${jobs.filter((j) => j.station === "fail").length} failed`,
            "polling 5s",
          ]}
        />
      </div>
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={null}>
      <JobsPageInner />
    </Suspense>
  );
}
