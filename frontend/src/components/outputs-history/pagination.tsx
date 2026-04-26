"use client";

import { useRouter, useSearchParams } from "next/navigation";

export interface PaginationProps {
  page: number;
  limit: number;
  total: number;
}

export function Pagination({ page, limit, total }: PaginationProps) {
  const router = useRouter();
  const params = useSearchParams();
  const totalPages = Math.max(1, Math.ceil(total / limit));

  function go(target: number) {
    const next = new URLSearchParams(params.toString());
    if (target <= 1) next.delete("page");
    else next.set("page", String(target));
    const qs = next.toString();
    router.push(qs ? `/outputs?${qs}` : "/outputs");
  }

  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <nav
      data-testid="pagination"
      aria-label="Outputs pagination"
      className="flex items-center gap-3 text-sm"
    >
      <button
        type="button"
        onClick={() => go(page - 1)}
        disabled={!canPrev}
        className="rounded border px-3 py-1 disabled:opacity-40"
      >
        Prev
      </button>
      <span data-testid="page-label" className="text-muted-foreground">
        Page {page} of {totalPages} · {total} total
      </span>
      <button
        type="button"
        onClick={() => go(page + 1)}
        disabled={!canNext}
        className="rounded border px-3 py-1 disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}
