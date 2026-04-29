"use client";

import React from "react";
import { usePathname, useRouter } from "next/navigation";
import { EgLogo } from "./components";
import { logout } from "@/lib/auth";

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

export interface SidebarConversation {
  id: string;
  title: string;
}

interface SidebarStats {
  indexed: number;
  stale: number;
  lastSync: string;
}

interface SidebarProps {
  rail?: boolean;
  onToggleRail?: () => void;
  conversations?: SidebarConversation[];
  onNewChat?: () => void;
  onSelectConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  stats?: SidebarStats;
}

/* ------------------------------------------------------------------ */
/*  Nav items                                                         */
/* ------------------------------------------------------------------ */

interface NavItem {
  id: string;
  k: string;
  c: string;
  label: string;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "workspace",   k: "01", c: "ASK", label: "workspace",   path: "/" },
  { id: "connections", k: "02", c: "SRC", label: "connections", path: "/connections" },
  { id: "library",     k: "03", c: "LIB", label: "library",     path: "/library" },
  { id: "jobs",        k: "04", c: "JOB", label: "jobs",        path: "/jobs" },
  { id: "outputs",     k: "05", c: "OUT", label: "outputs",     path: "/outputs" },
  { id: "compare",     k: "06", c: "DIF", label: "compare",     path: "/compare" },
  { id: "settings",    k: "07", c: "CFG", label: "settings",    path: "/settings" },
];

/* ------------------------------------------------------------------ */
/*  Sidebar                                                           */
/* ------------------------------------------------------------------ */

export function Sidebar({
  conversations,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  stats,
}: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (item: NavItem) =>
    item.path === "/" ? pathname === "/" : pathname.startsWith(item.path);

  const navigate = (item: NavItem) => {
    router.push(item.path);
  };

  return (
    <nav
      style={{
        width: "100%",
        height: "100%",
        borderRight: "1px solid var(--ink)",
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Logo + user info */}
      <div
        style={{
          padding: "12px 12px 10px",
          borderBottom: "1px solid var(--ink)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <EgLogo size={14} />
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "0.04em",
            }}
          >
            engram
          </span>
          <span className="v3-marg">v0.1</span>
        </div>
        <div className="v3-marg" style={{ marginTop: 6 }}>
          workspace
        </div>
      </div>

      {/* Navigation */}
      <div
        style={{ padding: 0, flex: 1, overflowY: "auto" }}
        className="v3-scroll"
      >
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          return (
            <button
              key={item.id}
              onClick={() => navigate(item)}
              style={{
                display: "grid",
                gridTemplateColumns: "30px 38px 1fr 12px",
                alignItems: "center",
                gap: 0,
                padding: "0 10px",
                height: 26,
                width: "100%",
                background: active ? "var(--ink)" : "transparent",
                color: active ? "var(--bg)" : "var(--ink)",
                textDecoration: "none",
                fontSize: 12,
                letterSpacing: "0.04em",
                borderBottom: "1px solid var(--line)",
                borderTop: "none",
                borderLeft: "none",
                borderRight: "none",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                textAlign: "left",
              }}
            >
              <span
                style={{
                  color: active ? "var(--accent)" : "var(--ink-4)",
                  fontSize: 11,
                }}
              >
                {item.k}
              </span>
              <span
                style={{
                  color: active ? "var(--accent)" : "var(--ink-3)",
                  fontSize: 10.5,
                }}
              >
                {item.c}
              </span>
              <span>{item.label}</span>
              <span
                style={{
                  color: active ? "var(--accent)" : "transparent",
                }}
              >
                {"\u203A"}
              </span>
            </button>
          );
        })}

        {/* Recent conversations */}
        {conversations && conversations.length > 0 && (
          <div
            style={{
              borderTop: "1px solid var(--ink)",
              padding: "8px 0",
            }}
          >
            <div
              style={{
                padding: "0 12px 6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span className="v3-cap">history</span>
              {onNewChat && (
                <button
                  onClick={onNewChat}
                  style={{
                    background: "var(--accent)",
                    color: "var(--accent-ink)",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  + new
                </button>
              )}
            </div>
            {conversations.map((conv, i) => (
              <div
                key={conv.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "26px 1fr 16px",
                  gap: 6,
                  padding: "3px 12px",
                  alignItems: "center",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--ink-3)",
                }}
              >
                <span style={{ color: "var(--ink-4)" }}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <button
                  onClick={() => onSelectConversation?.(conv.id)}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    textAlign: "left",
                    color: "inherit",
                    padding: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {conv.title}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteConversation?.(conv.id);
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = "var(--err)";
                    e.currentTarget.style.background = "var(--err-soft)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = "var(--ink-4)";
                    e.currentTarget.style.background = "transparent";
                  }}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                    fontSize: 13,
                    color: "var(--ink-4)",
                    padding: "2px 6px",
                    lineHeight: 1,
                  }}
                  title="delete conversation"
                >
                  {"\u00D7"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom stats + sign out */}
      <div
        style={{
          padding: "8px 12px",
          borderTop: "1px solid var(--ink)",
          fontSize: 10.5,
          color: "var(--ink-3)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span>idx</span>
          <span style={{ color: "var(--ink)" }}>{stats?.indexed ?? "--"}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span>stale</span>
          <span style={{ color: stats?.stale ? "var(--warn)" : "var(--ink-4)" }}>{stats?.stale ?? "--"}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span>sync</span>
          <span style={{ color: "var(--ink)" }}>{stats?.lastSync ?? "--:--"}</span>
        </div>
        <button
          onClick={logout}
          style={{
            marginTop: 8,
            width: "100%",
            background: "transparent",
            border: "1px solid var(--ink-4)",
            color: "var(--ink-3)",
            fontFamily: "var(--font-mono)",
            fontSize: 10.5,
            padding: "3px 0",
            cursor: "pointer",
            letterSpacing: "0.04em",
          }}
        >
          {"[ sign out ]"}
        </button>
      </div>
    </nav>
  );
}

export default Sidebar;
