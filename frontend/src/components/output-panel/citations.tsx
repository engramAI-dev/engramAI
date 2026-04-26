import type { OutputPanelSource } from "../output-panel";

const LINE_HASH_RE = /#L(\d+)(?:-L(\d+))?$/;

function lineLabel(url: string): string | null {
  const match = LINE_HASH_RE.exec(url);
  if (!match) return null;
  const [, start, end] = match;
  return end && end !== start ? `L${start}-${end}` : `L${start}`;
}

function dedupe(
  sources: OutputPanelSource[]
): { top: OutputPanelSource; extras: number }[] {
  const groups = new Map<string, OutputPanelSource[]>();
  for (const s of sources) {
    const list = groups.get(s.documentId) ?? [];
    list.push(s);
    groups.set(s.documentId, list);
  }
  return Array.from(groups.values())
    .map((list) => {
      const sorted = [...list].sort(
        (a, b) => b.relevanceScore - a.relevanceScore
      );
      return { top: sorted[0], extras: sorted.length - 1 };
    })
    .sort((a, b) => b.top.relevanceScore - a.top.relevanceScore);
}

export function Citations({ sources }: { sources: OutputPanelSource[] }) {
  if (sources.length === 0) return null;
  const grouped = dedupe(sources);
  return (
    <section data-testid="citations" className="mt-4 border-t pt-3 text-xs">
      <h3 className="mb-1 font-medium text-muted-foreground">Sources</h3>
      <ol className="list-decimal space-y-0.5 pl-5">
        {grouped.map(({ top: s, extras }) => {
          const lines = lineLabel(s.url);
          return (
            <li key={s.chunkId}>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                {s.documentTitle}
                {lines && (
                  <span className="ml-1 text-muted-foreground">({lines})</span>
                )}
              </a>
              {extras > 0 && (
                <span className="ml-1 text-muted-foreground">
                  +{extras} more
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
