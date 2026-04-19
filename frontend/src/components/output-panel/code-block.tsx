"use client";

import { useEffect, useState } from "react";
import { codeToHtml, type BundledLanguage } from "shiki";

const SUPPORTED_LANGUAGES = new Set<string>([
  "python",
  "typescript",
  "javascript",
  "tsx",
  "jsx",
  "go",
  "rust",
  "json",
  "bash",
  "shell",
  "yaml",
  "markdown",
  "html",
  "css",
  "sql",
]);

export interface CodeBlockProps {
  code: string;
  language: string | undefined;
}

// D7 (reversible): re-highlights every render. Cheap-ish for short snippets,
// but if streaming + long code blocks become a perf problem, debounce or
// switch to "highlight on done only" by gating on an `isStreaming` prop.
export function CodeBlock({ code, language }: CodeBlockProps) {
  const lang = (language ?? "").toLowerCase();
  const supported = SUPPORTED_LANGUAGES.has(lang);
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    if (!supported) return;
    let cancelled = false;
    codeToHtml(code, { lang: lang as BundledLanguage, theme: "github-dark" })
      .then((out) => {
        if (!cancelled) setHtml(out);
      })
      .catch(() => {
        // Highlight failure → fall through to the plain <pre> branch by
        // leaving `html` as whatever it was. Render gates on `supported`
        // anyway, so a stale value can't be shown for an unsupported lang.
      });
    return () => {
      cancelled = true;
    };
  }, [code, lang, supported]);

  return (
    <div data-testid="code-block" className="my-3 overflow-hidden rounded-md border bg-muted">
      <div className="flex items-center justify-between border-b bg-muted/60 px-3 py-1.5 text-xs">
        <span className="font-mono text-muted-foreground">{lang || "text"}</span>
        <CopyButton text={code} />
      </div>
      {supported && html ? (
        <div
          data-testid="shiki-output"
          className="overflow-x-auto p-3 text-sm"
          // Shiki output is trusted — produced from our own input, not user HTML.
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre data-testid="plain-pre" className="overflow-x-auto p-3 text-sm">
          <code className={lang ? `language-${lang}` : undefined}>{code}</code>
        </pre>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy code"
      className="rounded px-2 py-0.5 text-xs hover:bg-muted-foreground/10"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
