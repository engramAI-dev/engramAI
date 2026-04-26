"use client";

/**
 * A14 — Auth guard. Redirects to /login if no token.
 * Uses useSyncExternalStore to avoid both hydration mismatch and setState-in-effect.
 */

import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { useRouter } from "next/navigation";

const TOKEN_KEY = "engram_token";

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
}

function getClientSnapshot(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function getServerSnapshot(): string | null {
  return null;
}

function useToken(): string | null {
  return useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useToken();

  // On the server and first client render, token is null (getServerSnapshot).
  // After hydration, useSyncExternalStore calls getClientSnapshot and re-renders
  // if the value differs — no setState needed.

  useEffect(() => {
    // Only redirect after hydration (token will be null from server snapshot initially)
    // Wait a tick so useSyncExternalStore can sync
    const timer = setTimeout(() => {
      if (!localStorage.getItem(TOKEN_KEY)) {
        router.replace("/login");
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [token, router]);

  // Server render and initial hydration: show loading (matches both sides)
  // After sync: show children if token exists, loading if not
  if (!token) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return <>{children}</>;
}
