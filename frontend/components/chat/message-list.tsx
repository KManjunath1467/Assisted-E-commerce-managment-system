"use client";

import { useEffect, useRef } from "react";
import { AlertCircle, Bot, ShoppingBag } from "lucide-react";
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
  "Why did sales drop yesterday?",
  "Which products are low on stock?",
  "How are my campaigns performing?",
  "Show me recent customer support issues.",
];

function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-6 pt-12 text-center">
      <div className="flex size-14 items-center justify-center rounded-md border border-primary/20 bg-primary/10">
        <ShoppingBag className="size-6 text-primary" />
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
      <div className="mt-1 flex flex-wrap justify-center gap-2">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSend(prompt)}
            className="cursor-pointer rounded border border-border px-3 py-1.5 text-[0.75rem] font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {prompt}
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
                  <div className="flex w-full max-w-3xl items-end gap-2">
                    <div className="mb-5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Bot className="size-4" />
                    </div>
                    <div className="flex flex-1 flex-col items-start gap-1">
                      {msg.streamedText ? (
                        <div className="w-full rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-3.5 shadow-sm">
                          <p className="text-sm leading-relaxed text-foreground/90 font-[450] whitespace-pre-wrap">
                            {msg.streamedText}
                            <span className="inline-block w-1.5 h-4 ml-0.5 bg-primary/60 animate-pulse rounded-sm align-text-bottom" />
                          </p>
                        </div>
                      ) : (
                        <StreamingProgress currentNode={msg.currentNode} />
                      )}
                    </div>
                  </div>
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
