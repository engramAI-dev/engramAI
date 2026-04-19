import type { OutputPanelSource } from "../output-panel";

export function Citations({ sources }: { sources: OutputPanelSource[] }) {
  if (sources.length === 0) return null;
  return (
    <section data-testid="citations" className="mt-4 border-t pt-3 text-xs">
      <h3 className="mb-1 font-medium text-muted-foreground">Sources</h3>
      <ol className="list-decimal space-y-0.5 pl-5">
        {sources.map((s, i) => (
          <li key={`${s.chunkId}-${i}`}>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              {s.documentTitle}
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}
