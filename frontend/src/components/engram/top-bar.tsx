"use client";

import React from "react";

/* ------------------------------------------------------------------ */
/*  TopBar — v3 terminal titlebar (26px)                              */
/*  Accepts both v3 props (path/right) and legacy props               */
/*  (title/subtitle/icon/actions) for backward compatibility.         */
/* ------------------------------------------------------------------ */

interface TopBarProps {
  /** v3: full terminal-style path text */
  path?: string;
  /** v3: right-slot content */
  right?: React.ReactNode;
  /** legacy: page title — rendered as part of path when no path given */
  title?: string;
  /** legacy: subtitle text — appended after title */
  subtitle?: string;
  /** legacy: icon element — ignored in v3 */
  icon?: React.ReactNode;
  /** legacy: action buttons — mapped to right slot */
  actions?: React.ReactNode;
}

export function TopBar({
  path,
  right,
  title,
  subtitle,
  actions,
}: TopBarProps) {
  const displayPath =
    path ?? `engram@core:~/${title ? title.toLowerCase() : ""}$${subtitle ? " " + subtitle : ""}`;
  const displayRight = right ?? actions ?? null;

  return (
    <div className="v3-titlebar">
      <span className="dot" />
      <span className="dot" style={{ opacity: 0.6 }} />
      <span className="dot" style={{ opacity: 0.3 }} />
      <span style={{ marginLeft: 8 }}>{displayPath}</span>
      <span style={{ flex: 1 }} />
      {displayRight}
    </div>
  );
}

export default TopBar;
