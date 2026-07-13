"use client";

/**
 * App route group layout — wraps all authenticated pages with
 * AuthGuard, ChatProvider, Sidebar, and theme management.
 * v3 "Datasheet / CRT" design.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/lib/auth-guard";
import { apiFetch } from "@/lib/api";
import { ChatProvider, useChat } from "@/lib/chat-context";
import { getActiveWorkspace } from "@/lib/workspace";
import { WorkspaceNameContext } from "@/lib/workspace-context";
import { Sidebar, type SidebarConversation } from "@/components/engram/sidebar";

// -------------------------------------------------------------------
// Theme persistence
// -------------------------------------------------------------------

type Theme = "light" | "dark";
type Accent = "phosphor" | "amber" | "ibm-blue" | "redline" | "ink";
type Density = "comfortable" | "compact";

function subscribeLs(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}
function useLsPref<T extends string>(key: string, fallback: T): [T, (v: T) => void] {
  const value = useSyncExternalStore(
    subscribeLs,
    () => (localStorage.getItem(key) as T) || fallback,
    () => fallback,
  );
  const set = useCallback(
    (v: T) => {
      localStorage.setItem(key, v);
      // trigger subscribers in this tab
      window.dispatchEvent(new StorageEvent("storage", { key }));
    },
    [key],
  );
  return [value, set];
}

// -------------------------------------------------------------------
// Inner layout (needs ChatProvider already mounted)
// -------------------------------------------------------------------

function AppShellInner({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { conversations, newChat, loadConversation, loadConversations, deleteConversation } = useChat();

  const [sidebarStats, setSidebarStats] = useState<{ indexed: number; stale: number; lastSync: string } | undefined>();
  const [workspaceName, setWorkspaceName] = useState<string | undefined>();

  useEffect(() => {
    loadConversations().catch(() => {});

    // Resolve the active workspace's name for the sidebar header. The list
    // endpoint is the source of truth; localStorage only holds the id (and
    // may be empty, in which case the backend scopes to the default).
    apiFetch<{ workspaces: { id: string; name: string; is_default: boolean }[] }>("/api/teams")
      .then((data) => {
        const list = data.workspaces ?? [];
        const activeId = getActiveWorkspace();
        const active =
          list.find((w) => w.id === activeId) ?? list.find((w) => w.is_default) ?? list[0];
        if (active) setWorkspaceName(active.name);
      })
      .catch(() => {});

    // No global onboarding gate: login lands on the dashboard and per-workspace
    // setup is reached deliberately from there, so the app shell no longer
    // force-redirects to /onboarding.

    // Fetch sidebar stats
    apiFetch<{ documents: { indexed_at: string }[]; total: number }>("/api/documents/")
      .then((data) => {
        const total = data.total ?? data.documents?.length ?? 0;
        const now = Date.now();
        const stale = (data.documents ?? []).filter((d) => {
          if (!d.indexed_at) return true;
          return now - new Date(d.indexed_at).getTime() > 30 * 24 * 60 * 60 * 1000;
        }).length;
        const latest = (data.documents ?? [])
          .map((d) => d.indexed_at)
          .filter(Boolean)
          .sort()
          .pop();
        const syncTime = latest
          ? new Date(latest).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "--:--";
        setSidebarStats({ indexed: total, stale, lastSync: syncTime });
      })
      .catch(() => {});
  }, [loadConversations, router]);

  const handleNewChat = useCallback(() => {
    newChat();
    router.push("/");
  }, [newChat, router]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      loadConversation(id).catch(() => {
        /* ignore */
      });
      router.push(`/?c=${id}`);
    },
    [loadConversation, router],
  );

  const sidebarConversations: SidebarConversation[] = conversations.slice(0, 5).map((c) => ({
    id: c.id,
    title: c.title || "Untitled",
  }));

  const [sidebarWidth, setSidebarWidth] = useState(180);
  const dragging = useRef(false);

  const handleMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const w = Math.max(120, Math.min(400, e.clientX));
      setSidebarWidth(w);
    };
    const handleMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, []);

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--bg)" }}>
      <div style={{ width: sidebarWidth, flexShrink: 0 }}>
        <Sidebar
          conversations={sidebarConversations}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={(id) => {
            deleteConversation(id).catch(() => {});
          }}
          stats={sidebarStats}
          workspaceName={workspaceName}
        />
      </div>
      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          width: 4,
          cursor: "col-resize",
          background: "var(--bg)",
          flexShrink: 0,
          position: "relative",
        }}
      >
        <div style={{
          position: "absolute",
          top: 0, bottom: 0, left: 1,
          width: 2,
          background: "transparent",
          transition: "background 150ms",
        }} />
      </div>
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "auto",
          minWidth: 0,
          overflowWrap: "break-word" as const,
        }}
      >
        <WorkspaceNameContext.Provider value={workspaceName}>
          {children}
        </WorkspaceNameContext.Provider>
      </main>
    </div>
  );
}

// -------------------------------------------------------------------
// Outer layout (provides theme wrapper + providers)
// -------------------------------------------------------------------

export default function AppLayout({ children }: { children: ReactNode }) {
  const [theme] = useLsPref<Theme>("engram_theme", "dark");
  const [accent] = useLsPref<Accent>("engram_accent", "phosphor");
  const [density] = useLsPref<Density>("engram_density", "comfortable");

  const themeAttrs = {
    "data-theme": theme,
    "data-accent": accent,
    "data-density": density === "compact" ? ("compact" as const) : undefined,
  };

  return (
    <div
      {...themeAttrs}
      className={theme === "dark" ? "v3-scan" : undefined}
      style={{ height: "100%", background: "var(--bg)", color: "var(--ink)" }}
    >
      <AuthGuard>
        <ChatProvider>
          <AppShellInner>{children}</AppShellInner>
        </ChatProvider>
      </AuthGuard>
    </div>
  );
}
