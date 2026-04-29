"use client";

// B9 — Output history list view.
// Client-rendered: A's auth lives in localStorage, so server-side fetching
// can't attach a bearer token. URL-driven filter + pagination state preserved.

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { listOutputs, ApiError, type OutputListResponse, type OutputType } from "@/lib/api";
import { TypeFilter } from "@/components/outputs-history/type-filter";
import { Pagination } from "@/components/outputs-history/pagination";
import { OutputList } from "@/components/outputs-history/output-list";

const VALID_TYPES = new Set<OutputType>(["code_snippet", "summary", "report"]);
const LIMIT = 20;

export default function OutputsPage() {
  const searchParams = useSearchParams();
  const rawType = searchParams.get("type");
  const type: OutputType | undefined = VALID_TYPES.has(rawType as OutputType)
    ? (rawType as OutputType)
    : undefined;
  const pageNum = Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1);

  const [data, setData] = useState<OutputListResponse | null>(null);
  const [errStatus, setErrStatus] = useState(0);
  const [errMessage, setErrMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listOutputs({ type, page: pageNum, limit: LIMIT })
      .then((r) => {
        if (cancelled) return;
        setData(r);
        setErrStatus(0);
        setErrMessage("");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setData(null);
        setErrStatus(err instanceof ApiError ? err.status : 0);
        setErrMessage(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [type, pageNum]);

  const total = data?.total ?? 0;

  return (
    <main data-testid="outputs-page" className="mx-auto max-w-3xl space-y-4 px-4 py-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold">Outputs</h1>
        <TypeFilter active={type ?? "all"} />
      </header>
      {loading ? (
        <p data-testid="outputs-loading" className="text-sm text-muted-foreground">
          Loading…
        </p>
      ) : data ? (
        <OutputList items={data.outputs} />
      ) : (
        <div
          data-testid="outputs-error"
          role="alert"
          className="rounded border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
        >
          Couldn&apos;t load outputs{errStatus ? ` (${errStatus})` : ""}: {errMessage}
        </div>
      )}
      <Pagination page={pageNum} limit={LIMIT} total={total} />
    </main>
  );
}
