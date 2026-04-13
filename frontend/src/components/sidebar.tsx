"use client";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";

export function Sidebar() {
  return (
    <aside className="flex w-64 flex-col border-r bg-muted/30">
      <div className="flex h-14 items-center px-4 font-semibold">
        Engram
      </div>
      <Separator />
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start">
          + New Chat
        </Button>
      </div>
      <ScrollArea className="flex-1 px-3">
        <nav className="flex flex-col gap-1">
          {/* Chat history items will go here */}
          <p className="px-2 py-8 text-center text-sm text-muted-foreground">
            No conversations yet
          </p>
        </nav>
      </ScrollArea>
      <Separator />
      <div className="p-3">
        <Button variant="ghost" className="w-full justify-start text-sm">
          Settings
        </Button>
      </div>
    </aside>
  );
}
