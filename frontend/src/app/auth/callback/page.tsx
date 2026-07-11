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
        router.replace("/dashboard");
      }, 100);
    } else {
      setTimeout(() => {
        router.replace("/login");
      }, 1000);
    }
  }, [router]);

  return (
    <div
      className="v3-screen v3-scan"
      data-theme="dark"
      data-accent="phosphor"
      style={{ alignItems: "center", justifyContent: "center" }}
    >
      <p style={{ color: "var(--ink-3)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
        signing in...
      </p>
    </div>
  );
}
