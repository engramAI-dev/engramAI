"use client";

import React, { useState, useEffect, useSyncExternalStore, useCallback } from "react";
import {
  V3Tag,
  V3TitleBar,
  V3StatusBar,
  V3Hr,
} from "@/components/engram/components";
import { apiFetch } from "@/lib/api";
import { logout } from "@/lib/auth";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface UserInfo {
  id: string;
  github_username: string;
  avatar_url?: string;
  created_at: string;
}

interface UsageData {
  messages: number;
  input_tokens: number;
  output_tokens: number;
}

interface ModelOption {
  id: string;
  name: string;
  desc: string;
  current: boolean;
}

const MODELS: ModelOption[] = [
  { id: "gem", name: "gemini-2.5-flash", desc: "free · 15 rpm · default", current: true },
  { id: "hai", name: "claude-haiku-4.5", desc: "$0.25 / $1.25 per 1m", current: false },
  { id: "son", name: "claude-sonnet-4", desc: "$3 / $15 per 1m · best for code", current: false },
];

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

function subscribeLs(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}
function useLs(key: string, fallback: string): string {
  return useSyncExternalStore(
    subscribeLs,
    () => localStorage.getItem(key) || fallback,
    () => fallback,
  );
}

export default function SettingsPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [models, setModels] = useState<ModelOption[]>(MODELS);
  const currentTheme = useLs("engram_theme", "dark");
  const currentAccent = useLs("engram_accent", "phosphor");

  const setTheme = useCallback((v: string) => {
    localStorage.setItem("engram_theme", v);
    window.dispatchEvent(new StorageEvent("storage", { key: "engram_theme" }));
  }, []);
  const setAccent = useCallback((v: string) => {
    localStorage.setItem("engram_accent", v);
    window.dispatchEvent(new StorageEvent("storage", { key: "engram_accent" }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch<UserInfo>("/api/auth/me")
      .then((data) => { if (!cancelled) setUser(data); })
      .catch(() => {});
    apiFetch<UsageData>("/api/chat/usage")
      .then((data) => { if (!cancelled) setUsage(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  function selectModel(id: string) {
    setModels((prev) =>
      prev.map((m) => ({ ...m, current: m.id === id }))
    );
  }

  return (
    <div className="v3-screen v3-scan" style={{ flexDirection: "row" }}>
      <div
        className="v3-frame"
        style={{ flex: 1, border: "none", borderLeft: "1px solid var(--ink)" }}
      >
        <V3TitleBar path="engram@core:~/settings$ cat config" />

        <div className="v3-scroll" style={{ flex: 1, overflow: "auto" }}>
          <div style={{ maxWidth: 640, padding: "24px 28px" }}>

            {/* ── Account ── */}
            <span className="v3-cap">account</span>
            <V3Hr />
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "8px 16px", fontSize: 12, marginBottom: 24 }}>
              <span style={{ color: "var(--ink-3)" }}>user</span>
              <span style={{ color: "var(--accent)" }}>{user?.github_username || "..."}</span>
              <span style={{ color: "var(--ink-3)" }}>id</span>
              <span style={{ color: "var(--ink-4)", fontSize: 11 }}>{user?.id?.slice(0, 8) || "..."}</span>
              <span style={{ color: "var(--ink-3)" }}>method</span>
              <span><V3Tag tone="ok">GH-OAUTH</V3Tag></span>
              <span style={{ color: "var(--ink-3)" }}>joined</span>
              <span style={{ color: "var(--ink-4)" }}>{user?.created_at?.slice(0, 10) || "..."}</span>
            </div>

            {/* ── Usage (real data) ── */}
            <span className="v3-cap">usage</span>
            <V3Hr />
            {usage ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
                <div>
                  <div className="v3-bignum" style={{ color: "var(--accent)", fontSize: 32 }}>
                    {usage.messages}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 4 }}>messages</div>
                </div>
                <div>
                  <div className="v3-bignum" style={{ color: "var(--accent)", fontSize: 32 }}>
                    {formatTokens(usage.input_tokens)}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 4 }}>input tokens</div>
                </div>
                <div>
                  <div className="v3-bignum" style={{ color: "var(--accent)", fontSize: 32 }}>
                    {formatTokens(usage.output_tokens)}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 4 }}>output tokens</div>
                </div>
              </div>
            ) : (
              <div style={{ color: "var(--ink-4)", fontSize: 11, marginBottom: 24 }}>loading usage...</div>
            )}

            {/* ── Model ── */}
            <span className="v3-cap">model</span>
            <V3Hr />
            <div style={{ marginBottom: 24 }}>
              {models.map((m) => (
                <div
                  key={m.id}
                  onClick={() => selectModel(m.id)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "20px 1fr auto",
                    gap: 10,
                    alignItems: "center",
                    padding: "8px 0",
                    borderBottom: "1px dashed var(--line)",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  <span style={{ color: m.current ? "var(--accent)" : "var(--ink-4)", whiteSpace: "nowrap" }}>
                    {m.current ? "[x]" : "[\u00A0]"}
                  </span>
                  <span style={{ color: m.current ? "var(--ink)" : "var(--ink-3)" }}>{m.name}</span>
                  <span style={{ color: "var(--ink-4)", fontSize: 10 }}>
                    {m.desc}
                    {m.current && " \u25C0"}
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 8, fontSize: 10, color: "var(--ink-4)" }}>
                {`// model switching requires LLM_PROVIDER + LLM_MODEL in .env`}
              </div>
            </div>

            {/* ── Theme ── */}
            <span className="v3-cap">theme</span>
            <V3Hr />
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "8px 16px", fontSize: 12, marginBottom: 24 }}>
              <span style={{ color: "var(--ink-3)" }}>mode</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {(["light", "dark"] as const).map((m) => (
                  <button
                    key={m}
                    className="v3-btn"
                    data-size="sm"
                    data-variant={currentTheme === m ? "acc" : undefined}
                    onClick={() => setTheme(m)}
                  >
                    {m}{currentTheme === m ? " \u25C0" : ""}
                  </button>
                ))}
              </div>
              <span style={{ color: "var(--ink-3)" }}>accent</span>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(["phosphor", "amber", "ibm-blue", "redline", "ink"] as const).map((a) => (
                  <button
                    key={a}
                    className="v3-btn"
                    data-size="sm"
                    data-variant={currentAccent === a ? "acc" : undefined}
                    onClick={() => setAccent(a)}
                  >
                    {a}{currentAccent === a ? " \u25C0" : ""}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Danger ── */}
            <span className="v3-cap">danger zone</span>
            <V3Hr />
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button
                className="v3-btn"
                style={{ borderColor: "var(--err)", color: "var(--err)" }}
                onClick={async () => {
                  if (!window.confirm("Wipe library? All indexed documents will be deleted and you will need to re-index everything.")) return;
                  try {
                    const res = await apiFetch<{ documents_deleted: number; ingest_jobs_deleted: number }>(
                      "/api/admin/wipe-library",
                      { method: "POST" },
                    );
                    // The Jobs tab reads from this localStorage cache (jobs/page.tsx:STORAGE_KEY).
                    // Without clearing it, the UI keeps showing job IDs whose DB rows we just deleted.
                    localStorage.removeItem("engram_job_ids");
                    window.alert(`Library wiped: ${res.documents_deleted} documents, ${res.ingest_jobs_deleted} jobs deleted.`);
                    window.location.reload();
                  } catch (e) {
                    window.alert(`Wipe failed: ${(e as Error).message}`);
                  }
                }}
              >
                wipe library
              </button>
              {process.env.NEXT_PUBLIC_DEBUG === "1" && (
                <button
                  className="v3-btn"
                  style={{ borderColor: "var(--err)", color: "var(--err)" }}
                  title="Developer-only: drops the Notion connection so re-OAuth can be tested."
                  onClick={async () => {
                    if (!window.confirm("[debug] Disconnect Notion? You will need to re-authorize.")) return;
                    try {
                      const res = await apiFetch<{ provider: string; deleted: boolean }>(
                        "/api/admin/disconnect/notion",
                        { method: "POST" },
                      );
                      window.alert(res.deleted ? "Notion disconnected." : "No Notion connection found.");
                      window.location.reload();
                    } catch (e) {
                      window.alert(`Disconnect failed: ${(e as Error).message}`);
                    }
                  }}
                >
                  [debug] disconnect notion
                </button>
              )}
              <button
                className="v3-btn"
                style={{ borderColor: "var(--err)", color: "var(--err)" }}
                onClick={() => logout()}
              >
                sign out
              </button>
            </div>
          </div>
        </div>

        <V3StatusBar
          items={[
            user?.github_username || "...",
            `${usage?.messages ?? 0} msgs`,
            `${formatTokens(usage?.input_tokens ?? 0)} in`,
            `${formatTokens(usage?.output_tokens ?? 0)} out`,
          ]}
        />
      </div>
    </div>
  );
}
