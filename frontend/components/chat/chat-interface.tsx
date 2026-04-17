"use client";

import { useState } from "react";
import Link from "next/link";
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

function newId(): string {
  return crypto.randomUUID();
}

function rebuildMessages(items: ThreadMessageItem[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  for (const item of items) {
    if (item.role === "user") {
      const msg: UserMessage = {
        id: newId(),
        type: "user",
        text: (item.content.text as string) ?? "",
        timestamp: item.created_at,
      };
      messages.push(msg);
    } else {
      const content = item.content as Record<string, unknown>;
      if (content.status === "complete" && content.report) {
        const msg: ReportMessage = {
          id: newId(),
          type: "report",
          report: content.report as ReportMessage["report"],
          thread_id: content.thread_id as string,
          timestamp: item.created_at,
        };
        messages.push(msg);
      } else if (content.status === "pending_approval") {
        const msg: PendingApprovalMessage = {
          id: newId(),
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
          id: newId(),
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
            <Link href="/incidents">
              <Button variant="ghost" size="sm" className="text-xs gap-1.5">
                <AlertCircle className="size-3.5" />
                Incidents
              </Button>
            </Link>
            <Link href="/actions">
              <Button variant="ghost" size="sm" className="text-xs gap-1.5">
                <Zap className="size-3.5" />
                Actions
              </Button>
            </Link>
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
          <p className="mt-2 text-center text-[0.65rem] font-medium text-muted-foreground">
            Shift+Enter for a new line · Enter to send
          </p>
        </div>
      </div>
    </div>
  );
}
