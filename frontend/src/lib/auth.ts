/**
 * A14 — Auth utilities (D46: localStorage).
 */

const TOKEN_KEY = "engram_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function logout(): void {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  // Best-effort server-side revoke of the cookie session; navigate regardless.
  fetch(`${apiBase}/api/auth/logout`, { method: "POST", credentials: "include" })
    .catch(() => {})
    .finally(() => {
      removeToken();
      window.location.href = "/login";
    });
}

export function getLoginUrl(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${apiBase}/api/auth/login`;
}
