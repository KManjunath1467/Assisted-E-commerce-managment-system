"use client";

import { useEffect, useRef } from "react";
import {
  AlertCircle,
  BarChart2,
  Package,
  Megaphone,
  MessageCircle,
} from "lucide-react";
import { HitlActionCard } from "@/components/chat/hitl-action-card";
import { MessageBubble } from "@/components/chat/message-bubble";
import { StreamingProgress } from "@/components/chat/message-skeleton";
import { ReportCard } from "@/components/chat/report-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage } from "@/lib/types";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  onSend: (text: string) => void;
  onApprove: (
    messageId: string,
    actionId: string,
    approved: boolean,
  ) => Promise<void>;
}

const EXAMPLE_PROMPTS = [
  { text: "Why did sales drop yesterday?", icon: BarChart2 },
  { text: "Which products are low on stock?", icon: Package },
  { text: "How are my campaigns performing?", icon: Megaphone },
  { text: "Show me recent customer support issues.", icon: MessageCircle },
];

function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 px-6 pt-12 text-center">
      <div className="relative flex size-14 items-center justify-center rounded-xl border border-primary/20 bg-primary/10">
        <div className="absolute inset-0 rounded-xl bg-gradient-to-b from-primary/5 to-primary/20" />
        <BarChart2 className="relative size-6 text-primary" />
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">
          E-commerce Operations Assistant
        </p>
        <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
          Ask anything about your sales, inventory, marketing, or customer
          support.
        </p>
      </div>
      <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {EXAMPLE_PROMPTS.map(({ text, icon: Icon }) => (
          <button
            key={text}
            type="button"
            onClick={() => onSend(text)}
            className="flex cursor-pointer items-center gap-2 rounded-lg bg-secondary px-3 py-2 text-left text-[0.75rem] font-medium text-secondary-foreground transition-all hover:bg-accent hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon className="size-3.5 shrink-0 text-muted-foreground" />
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function ErrorBubble({ text }: { text: string }) {
  return (
    <div className="flex w-full max-w-3xl items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
      <p className="text-sm text-destructive">{text}</p>
    </div>
  );
}

export function MessageList({ messages, isLoading, onSend, onApprove }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages change or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <ScrollArea className="flex-1 min-h-0">
      <div className="flex min-h-full flex-col">
        {isEmpty ? (
          <EmptyState onSend={onSend} />
        ) : (
          <div className="flex flex-col gap-4 px-4 py-6 sm:px-6">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className="animate-in fade-in slide-in-from-bottom-2 duration-300 flex w-full"
                style={{
                  justifyContent:
                    msg.type === "user" ? "flex-end" : "flex-start",
                }}
              >
                {msg.type === "user" && <MessageBubble message={msg} />}
                {msg.type === "report" && <ReportCard message={msg} />}
                {msg.type === "pending_approval" && (
                  <HitlActionCard message={msg} onApprove={onApprove} />
                )}
                {msg.type === "error" && <ErrorBubble text={msg.text} />}
                {msg.type === "streaming" && (
                  <StreamingProgress currentNode={msg.currentNode} />
                )}
              </div>
            ))}

            {/* Invisible scroll anchor */}
            <div ref={bottomRef} className="h-px" />
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
