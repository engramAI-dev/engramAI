"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./code-block";

const COMPONENTS: Components = {
  code({ className, children, ...rest }) {
    const text = String(children ?? "").replace(/\n$/, "");
    const langMatch = /language-([\w+-]+)/.exec(className ?? "");
    const isFenced = Boolean(langMatch) || text.includes("\n");
    if (!isFenced) {
      return (
        <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]" {...rest}>
          {children}
        </code>
      );
    }
    return <CodeBlock code={text} language={langMatch?.[1]} />;
  },
  a({ href, children, ...rest }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline" {...rest}>
        {children}
      </a>
    );
  },
};

export function Markdown({ children }: { children: string }) {
  return (
    <div data-testid="markdown" className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
