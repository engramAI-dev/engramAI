import Link from "next/link";
import type { OutputListItem } from "@/lib/api";

const TYPE_LABEL: Record<OutputListItem["type"], string> = {
  code_snippet: "Code",
  summary: "Summary",
  report: "Report",
};

function formatRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return `${Math.max(0, sec)}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return then.toLocaleDateString();
}

export function OutputList({ items }: { items: OutputListItem[] }) {
  if (items.length === 0) {
    return (
      <p data-testid="outputs-empty" className="rounded border border-dashed p-6 text-center text-muted-foreground">
        No outputs yet. Generate one from the chat panel and it&apos;ll show up here.
      </p>
    );
  }
  return (
    <ul data-testid="outputs-list" className="divide-y rounded border">
      {items.map((o) => (
        <li key={o.id} data-testid="outputs-row" className="hover:bg-muted">
          <Link href={`/outputs/${o.id}`} className="block px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="truncate text-base font-medium">{o.title}</h2>
              <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                {TYPE_LABEL[o.type]}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{o.preview}</p>
            <p className="mt-1 text-xs text-muted-foreground">{formatRelative(o.created_at)}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
