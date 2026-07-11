"use client";

/**
 * Dashboard — the universal post-login home.
 *
 * Lists the user's workspaces (GET /api/teams) and, when the plan allows it,
 * lets them create one. Multi-workspace creation is a paid/private capability,
 * so the create control is shown only when `can_create_teams` is enabled — in
 * the OSS build it stays hidden and users work in their single default
 * workspace. Deliberately outside the (app) route group so it doesn't mount the
 * workspace-scoped chat shell.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/lib/auth-guard";
import { apiFetch } from "@/lib/api";
import { V3TitleBar, V3StatusBar, V3Hr, EgLogo } from "@/components/engram/components";

type Workspace = {
  id: string;
  name: string;
  slug: string;
  plan: string;
  role: string;
  is_default: boolean;
  onboarding_state: string | null;
};

type Badge = "ready" | "indexing" | "needs-setup";

function badgeFor(w: Workspace): Badge {
  if (w.onboarding_state === "ready") return "ready";
  if (w.onboarding_state === "indexing") return "indexing";
  return "needs-setup";
}

const BADGE_LABEL: Record<Badge, string> = {
  ready: "ready",
  indexing: "indexing…",
  "needs-setup": "needs setup",
};

const BADGE_COLOR: Record<Badge, string> = {
  ready: "var(--accent)",
  indexing: "var(--ink-2)",
  "needs-setup": "var(--ink-3)",
};

function DashboardInner() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [canCreate, setCanCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiFetch<{ workspaces: Workspace[] }>("/api/teams")
      .then((data) => setWorkspaces(data.workspaces))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"));
    // Entitlements gate the create control (paid/private capability).
    apiFetch<{ entitlements: { can_create_teams?: boolean } }>("/api/teams/current")
      .then((t) => setCanCreate(Boolean(t.entitlements?.can_create_teams)))
      .catch(() => setCanCreate(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const enter = useCallback(
    (w: Workspace) => {
      router.push(badgeFor(w) === "ready" ? "/" : "/onboarding");
    },
    [router],
  );

  const create = useCallback(async () => {
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch<{ id: string }>("/api/teams", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      router.push("/onboarding");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create workspace");
      setBusy(false);
    }
  }, [newName, busy, router]);

  return (
    <div
      className="v3-screen v3-scan"
      data-theme="dark"
      data-accent="phosphor"
      style={{ alignItems: "center", justifyContent: "flex-start", padding: 24, overflow: "auto" }}
    >
      <div style={{ width: 640, maxWidth: "100%", marginTop: 32 }}>
        <div className="v3-frame" style={{ height: "auto" }}>
          <V3TitleBar
            path="engram@core:~$ workspaces --list"
            right={<span style={{ color: "var(--accent)" }}>{"●"}</span>}
          />

          <div style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <EgLogo size={18} />
              <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "0.04em" }}>
                your workspaces
              </span>
            </div>

            {error && (
              <div style={{ color: "var(--redline, #e5484d)", fontSize: 12, marginBottom: 12 }}>
                {"// "}
                {error}
              </div>
            )}

            {workspaces === null && !error && (
              <p style={{ color: "var(--ink-3)", fontSize: 12 }}>loading…</p>
            )}

            {workspaces && workspaces.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
                {workspaces.map((w) => {
                  const b = badgeFor(w);
                  return (
                    <button
                      key={w.id}
                      className="v3-btn"
                      onClick={() => enter(w)}
                      style={{
                        width: "100%",
                        height: "auto",
                        padding: "10px 12px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        textAlign: "left",
                      }}
                    >
                      <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                        <span style={{ fontSize: 13, color: "var(--ink)" }}>{w.name}</span>
                        <span style={{ fontSize: 10.5, color: "var(--ink-4)" }}>
                          {w.role} · {w.plan}
                        </span>
                      </span>
                      <span style={{ fontSize: 10.5, color: BADGE_COLOR[b], whiteSpace: "nowrap" }}>
                        {"●"} {BADGE_LABEL[b]}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Create is a paid/private capability — hidden unless entitled. */}
            {canCreate && (
              <>
                <V3Hr />
                {creating ? (
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <input
                      autoFocus
                      placeholder="workspace name"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") create();
                        if (e.key === "Escape") setCreating(false);
                      }}
                      style={{
                        flex: 1,
                        height: 32,
                        padding: "0 10px",
                        fontSize: 13,
                        background: "var(--bg-2, #111)",
                        color: "var(--ink)",
                        border: "1px solid var(--ink-4)",
                      }}
                    />
                    <button
                      className="v3-btn"
                      data-variant="acc"
                      onClick={create}
                      disabled={busy || !newName.trim()}
                      style={{ height: 32, justifyContent: "center", minWidth: 96 }}
                    >
                      {busy ? "creating…" : "create →"}
                    </button>
                  </div>
                ) : (
                  <button
                    className="v3-btn"
                    data-variant="acc"
                    onClick={() => {
                      setError(null);
                      setCreating(true);
                    }}
                    style={{ marginTop: 12, height: 32, justifyContent: "center", minWidth: 180 }}
                  >
                    + create workspace
                  </button>
                )}
              </>
            )}
          </div>

          <V3StatusBar
            items={[
              <span key="online">
                <span style={{ color: "var(--accent)" }}>{"●"}</span> ONLINE
              </span>,
              workspaces ? `${workspaces.length} workspace${workspaces.length === 1 ? "" : "s"}` : "—",
              "us-west-2",
            ]}
          />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardInner />
    </AuthGuard>
  );
}
