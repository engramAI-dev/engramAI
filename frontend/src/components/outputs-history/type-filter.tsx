"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { OutputType } from "@/lib/api";

const PILLS: { value: OutputType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "code_snippet", label: "Code" },
  { value: "summary", label: "Summary" },
  { value: "report", label: "Report" },
];

export function TypeFilter({ active }: { active: OutputType | "all" }) {
  const router = useRouter();
  const params = useSearchParams();

  function pick(value: OutputType | "all") {
    const next = new URLSearchParams(params.toString());
    if (value === "all") next.delete("type");
    else next.set("type", value);
    next.delete("page"); // Reset to page 1 when changing filter.
    const qs = next.toString();
    router.push(qs ? `/outputs?${qs}` : "/outputs");
  }

  return (
    <div data-testid="type-filter" className="flex gap-2 text-sm">
      {PILLS.map((p) => {
        const selected = p.value === active;
        return (
          <button
            key={p.value}
            type="button"
            onClick={() => pick(p.value)}
            data-active={selected ? "true" : "false"}
            aria-pressed={selected}
            className={
              selected
                ? "rounded-full border border-foreground bg-foreground px-3 py-1 text-background"
                : "rounded-full border px-3 py-1 hover:bg-muted"
            }
          >
            {p.label}
          </button>
        );
      })}
    </div>
  );
}
