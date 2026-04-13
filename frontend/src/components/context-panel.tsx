"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export function ContextPanel() {
  return (
    <aside className="flex w-80 flex-col border-l bg-muted/10">
      <div className="flex h-14 items-center px-4">
        <h3 className="text-sm font-medium text-muted-foreground">Sources</h3>
      </div>
      <Separator />
      <ScrollArea className="flex-1 p-4">
        <p className="text-sm text-muted-foreground">
          Referenced sources will appear here when you ask a question.
        </p>
      </ScrollArea>
    </aside>
  );
}
