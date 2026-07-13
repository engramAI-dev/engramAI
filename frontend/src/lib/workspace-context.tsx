"use client";

/**
 * Active-workspace name, resolved once by the (app) layout and shared with
 * pages (F4: the chat landing shows which workspace you're in).
 */

import { createContext, useContext } from "react";

export const WorkspaceNameContext = createContext<string | undefined>(undefined);

export function useWorkspaceName(): string | undefined {
  return useContext(WorkspaceNameContext);
}

/** Render a workspace name as a terminal-path segment ("Acme's WS" → "acme-s-ws"). */
export function workspacePathSegment(name: string | undefined): string {
  if (!name) return "workspace";
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "workspace";
}
