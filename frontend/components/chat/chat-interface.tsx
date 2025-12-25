"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, Bot, Zap } from "lucide-react";
import { getThreadHistory } from "@/lib/api";
import type {
  ChatMessage,
  ErrorMessage,
  PendingApprovalMessage,
  ReportMessage,
  ThreadMessageItem,
  UserMessage,
} from "@/lib/types";
import { MessageList } from "@/components/chat/message-list";
import { QueryInput } from "@/components/chat/query-input";
import { Sidebar } from "@/components/chat/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { useChat } from "@/hooks/use-chat";
import { useThreads } from "@/hooks/use-threads";

function rebuildMessages(items: ThreadMessageItem[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  for (const item of items) {
    if (item.role === "user") {
      const msg: UserMessage = {
        id: item.id,
        type: "user",
        text: (item.content.text as string) ?? "",
        timestamp: item.created_at,
      };
      messages.push(msg);
    } else {
      const content = item.content as Record<string, unknown>;
      if (content.status === "complete" && content.report) {
        const msg: ReportMessage = {
          id: item.id,
          type: "report",
          report: content.report as ReportMessage["report"],
          thread_id: content.thread_id as string,
          timestamp: item.created_at,
        };
        messages.push(msg);
      } else if (content.status === "pending_approval") {
        const msg: PendingApprovalMessage = {
          id: item.id,
          type: "pending_approval",
          actions:
            (content.pending_actions as PendingApprovalMessage["actions"]) ??
            [],
          thread_id: content.thread_id as string,
          timestamp: item.created_at,
          resolvedActions: {},
          is_historical: true,
        };
        messages.push(msg);
      } else {
        const msg: ErrorMessage = {
          id: item.id,
          type: "error",
          text: "This message could not be replayed.",
          timestamp: item.created_at,
        };
        messages.push(msg);
      }
    }
  }
  return messages;
}

const NAV_LINKS = [
  { href: "/incidents", label: "Incidents", icon: AlertCircle },
  { href: "/actions", label: "Actions", icon: Zap },
];

export function ChatInterface() {
  const {
    messages,
    isLoading,
    activeThreadId,
    sendMessage,
    handleApprove,
    startNewChat,
    loadThread,
  } = useChat();
  const { threads, isLoading: threadsLoading, fetchThreads } = useThreads();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const pathname = usePathname();

  async function handleSendMessage(text: string) {
    await sendMessage(text);
    // Refresh sidebar so the new/updated thread appears immediately.
    fetchThreads();
  }

  async function handleLoadThread(threadId: string) {
    try {
      const items = await getThreadHistory(threadId);
      loadThread(threadId, rebuildMessages(items));
    } catch {
      // If history fetch fails, just switch to an empty thread
      loadThread(threadId, []);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden flex-row bg-background">
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <Sidebar
        threads={threads}
        isLoading={threadsLoading}
        activeThreadId={activeThreadId}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen((o) => !o)}
        onNewChat={startNewChat}
        onLoadThread={handleLoadThread}
      />

      {/* ── Main chat column ─────────────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        {/* Header */}
        <header className="flex shrink-0 items-center gap-3 px-4 py-3 sm:px-6 bg-background/90 backdrop-blur-sm border-b border-border shadow-sm">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Bot className="size-4" />
            </div>
            <div>
              <p className="text-sm font-semibold leading-none text-foreground">
                Operations Assistant
              </p>
              <p className="mt-0.5 text-[0.65rem] font-medium text-muted-foreground">
                E-commerce Intelligence
              </p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href;
              return (
                <Link key={href} href={href}>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`text-xs gap-1.5 ${
                      isActive ? "text-foreground font-semibold bg-muted" : ""
                    }`}
                  >
                    <Icon className="size-3.5" />
                    {label}
                  </Button>
                </Link>
              );
            })}
            <ThemeToggle />
          </div>
        </header>

        {/* Message list */}
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onSend={handleSendMessage}
          onApprove={handleApprove}
        />

        <Separator />

        {/* Input bar */}
        <div className="shrink-0 px-4 py-3 sm:px-6">
          <QueryInput onSend={handleSendMessage} isLoading={isLoading} />
          <p className="mt-2 text-left text-[0.65rem] font-medium text-muted-foreground">
            Shift+Enter for a new line · Enter to send
          </p>
        </div>
      </div>
    </div>
  );
}
