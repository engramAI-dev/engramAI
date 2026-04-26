"use client";

/**
 * A14 — Login page with GitHub OAuth button.
 */

import { Button } from "@/components/ui/button";
import { getLoginUrl } from "@/lib/auth";

export default function LoginPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Engram</h1>
          <p className="mt-2 text-muted-foreground">
            Engineering intelligence platform
          </p>
        </div>
        <Button
          size="lg"
          onClick={() => {
            window.location.href = getLoginUrl();
          }}
        >
          Sign in with GitHub
        </Button>
      </div>
    </div>
  );
}
