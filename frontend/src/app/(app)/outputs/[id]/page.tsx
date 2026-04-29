"use client";

// B9 — Output detail view.
// Client-rendered to match A's localStorage auth.

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { getOutput, ApiError, type OutputResponse } from "@/lib/api";
import { Markdown } from "@/components/output-panel/markdown";
import { CodeBlock } from "@/components/output-panel/code-block";

interface PageProps {
  params: Promise<{ id: string }>;
}

const TYPE_LABEL: Record<OutputResponse["type"], string> = {
  code_snippet: "Code",
  summary: "Summary",
  report: "Report",
};

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

export default function OutputDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [output, setOutput] = useState<OutputResponse | null>(null);
  const [errStatus, setErrStatus] = useState(0);
  const [errMessage, setErrMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getOutput(id)
      .then((r) => {
        if (cancelled) return;
        setOutput(r);
        setErrStatus(0);
        setErrMessage("");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setOutput(null);
        setErrStatus(err instanceof ApiError ? err.status : 0);
        setErrMessage(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main data-testid="output-detail-page" className="mx-auto max-w-3xl space-y-4 px-4 py-6">
      <Link href="/outputs" className="text-sm text-muted-foreground hover:underline">
        ← Outputs
      </Link>
      {loading ? (
        <p data-testid="output-loading" className="text-sm text-muted-foreground">
          Loading…
        </p>
      ) : output ? (
        <>
          <header className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded-full border px-2 py-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                {TYPE_LABEL[output.type]}
              </span>
              <span className="text-xs text-muted-foreground">
                {new Date(output.created_at).toLocaleString()}
              </span>
            </div>
            <h1 data-testid="output-title" className="text-2xl font-semibold">
              {output.title}
            </h1>
          </header>

          <section data-testid="output-content">
            {output.type === "code_snippet" ? (
              <CodeBlock code={output.content} language={output.metadata.language ?? undefined} />
            ) : (
              <Markdown>{output.content}</Markdown>
            )}
          </section>

          <footer
            data-testid="output-metadata"
            className="space-y-1 border-t pt-3 text-xs text-muted-foreground"
          >
            {output.metadata.language && <p>Language: {output.metadata.language}</p>}
            {output.metadata.file_path_suggestion && (
              <p>Suggested path: {output.metadata.file_path_suggestion}</p>
            )}
            <p>
              Source: message {shortId(output.metadata.source_message_id)} in conversation{" "}
              <Link
                href={`/?c=${output.metadata.source_conversation_id}`}
                className="underline hover:text-foreground"
              >
                {shortId(output.metadata.source_conversation_id)}
              </Link>
            </p>
            <p>
              <Link
                href={`/?c=${output.metadata.source_conversation_id}`}
                className="underline hover:text-foreground"
              >
                ← Open in chat
              </Link>
            </p>
          </footer>
        </>
      ) : errStatus === 404 ? (
        <div data-testid="output-not-found" role="alert" className="rounded border p-4 text-sm">
          Output not found.
        </div>
      ) : (
        <div
          data-testid="output-error"
          role="alert"
          className="rounded border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
        >
          Couldn&apos;t load output{errStatus ? ` (${errStatus})` : ""}: {errMessage}
        </div>
      )}
    </main>
  );
}
