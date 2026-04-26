"use client";

/**
 * A14 — OAuth callback page. Reads token from URL, stores it, redirects to /.
 */

import { useEffect } from "react";
import { setToken } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (token) {
      setToken(token);
      setTimeout(() => {
        router.replace("/");
      }, 100);
    } else {
      setTimeout(() => {
        router.replace("/login");
      }, 1000);
    }
  }, [router]);

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-muted-foreground">Signing in...</p>
    </div>
  );
}
