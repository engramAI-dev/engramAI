"use client";

// Bridge from A's chat to B's /outputs surface.
// Inline button row under each assistant message: "Save as: Code | Summary | Report".
// On success: status text + link to /outputs/{id}.

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { generateOutput, ApiError, type OutputType } from "@/lib/api";

interface SaveAsOutputProps {
  messageId: string;
}

const TYPES: { type: OutputType; label: string }[] = [
  { type: "code_snippet", label: "Code" },
  { type: "summary", label: "Summary" },
  { type: "report", label: "Report" },
];

export function SaveAsOutput({ messageId }: SaveAsOutputProps) {
  const [busy, setBusy] = useState<OutputType | null>(null);
  const [error, setError] = useState("");
  const [savedId, setSavedId] = useState("");

  async function onSave(type: OutputType) {
    setBusy(type);
    setError("");
    try {
      const out = await generateOutput(messageId, type);
      setSavedId(out.id);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div data-testid="save-as-output" className="mt-2 flex flex-wrap items-center gap-2 text-xs">
      <span className="text-muted-foreground">Save as:</span>
      {TYPES.map(({ type, label }) => (
        <Button
          key={type}
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() => onSave(type)}
        >
          {busy === type ? "..." : label}
        </Button>
      ))}
      {savedId && (
        <Link
          href={`/outputs/${savedId}`}
          data-testid="save-as-output-link"
          className="text-primary underline"
        >
          Saved → view
        </Link>
      )}
      {error && (
        <span data-testid="save-as-output-error" className="text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}
