"use client";

import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ThreadSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return new Date(iso).toLocaleDateString();
}

function getDateGroup(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const weekAgo = new Date(today);
  weekAgo.setDate(weekAgo.getDate() - 7);
  const threadDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  if (threadDay >= today) return "Today";
  if (threadDay >= yesterday) return "Yesterday";
  if (threadDay >= weekAgo) return "This Week";
  return "Older";
}

const GROUP_ORDER = ["Today", "Yesterday", "This Week", "Older"];

function groupThreads(
  threads: ThreadSummary[],
): { group: string; threads: ThreadSummary[] }[] {
  const map = new Map<string, ThreadSummary[]>();
  for (const thread of threads) {
    const g = getDateGroup(thread.updated_at);
    if (!map.has(g)) map.set(g, []);
    map.get(g)!.push(thread);
  }
  return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({
    group: g,
    threads: map.get(g)!,
  }));
}

interface Props {
  threads: ThreadSummary[];
  isLoading: boolean;
  activeThreadId: string | null;
  isOpen: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onLoadThread: (threadId: string) => void;
}

export function Sidebar({
  threads,
  isLoading,
  activeThreadId,
  isOpen,
  onToggle,
  onNewChat,
  onLoadThread,
}: Props) {
  const grouped = groupThreads(threads);

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r-2 border-sidebar-border bg-sidebar shadow-[2px_0_8px_-2px_rgba(0,0,0,0.08)] transition-all duration-200 dark:shadow-[2px_0_12px_-2px_rgba(0,0,0,0.4)]",
        isOpen ? "w-64" : "w-10",
      )}
    >
      {/* Toggle + New Chat row */}
      <div
        className={cn(
          "flex shrink-0 items-center py-3",
          isOpen ? "gap-1 px-2" : "flex-col gap-2 px-1",
        )}
      >
        <Tooltip>
          <TooltipTrigger
            className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={onToggle}
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isOpen ? (
              <PanelLeftClose className="size-4" />
            ) : (
              <PanelLeftOpen className="size-4" />
            )}
          </TooltipTrigger>
          <TooltipContent side="right">
            {isOpen ? "Collapse sidebar" : "Expand sidebar"}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={onNewChat}
            aria-label="New chat"
          >
            <MessageSquarePlus className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="right">New chat</TooltipContent>
        </Tooltip>
      </div>

      {isOpen && (
        <>
          <Separator />
          <div className="px-3 pb-1 pt-2">
            <p className="text-xs font-semibold text-foreground/80 truncate">
              Operations Assistant
            </p>
            <p className="text-[0.6rem] font-semibold uppercase tracking-widest text-muted-foreground mt-0.5">
              Recent chats
            </p>
          </div>
          <ScrollArea className="flex-1">
            {isLoading && threads.length === 0 ? (
              <div className="space-y-1 px-2">
                {[...Array(4)].map((_, i) => (
                  <div
                    key={i}
                    className="h-9 animate-pulse rounded-md bg-muted"
                  />
                ))}
              </div>
            ) : threads.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                No conversations yet
              </p>
            ) : (
              <div className="flex flex-col pb-4">
                {grouped.map(({ group, threads: groupThreads }) => (
                  <div key={group}>
                    <p className="px-3 pb-1 pt-3 text-[0.6rem] font-semibold uppercase tracking-widest text-muted-foreground">
                      {group}
                    </p>
                    <div className="flex flex-col gap-0.5 px-2">
                      {groupThreads.map((thread) => {
                        const isActive = activeThreadId === thread.thread_id;
                        return (
                          <button
                            key={thread.thread_id}
                            type="button"
                            onClick={() => onLoadThread(thread.thread_id)}
                            className={cn(
                              "flex w-full cursor-pointer flex-col items-start rounded py-2 text-left transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                              isActive
                                ? "border-l-2 border-primary pl-[10px] pr-3 bg-primary/8 text-foreground"
                                : "px-3",
                            )}
                          >
                            <span className="w-full truncate text-xs font-medium">
                              {thread.title}
                            </span>
                            <span className="mt-0.5 text-[0.65rem] font-medium text-muted-foreground">
                              {relativeTime(thread.updated_at)}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </>
      )}
    </aside>
  );
}
