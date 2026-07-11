/**
 * Active-workspace tracking (2026-07-11 re-home).
 *
 * The backend scopes every request to a workspace via the `X-Workspace-Id`
 * header. The active workspace is chosen when the user enters (or creates) one
 * from the dashboard and persisted in localStorage so it survives reloads and
 * is sent on every API call. Absent → the backend falls back to the user's
 * most-recent workspace.
 */

const ACTIVE_KEY = "engram_active_workspace";

export function getActiveWorkspace(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveWorkspace(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function clearActiveWorkspace(): void {
  localStorage.removeItem(ACTIVE_KEY);
}
