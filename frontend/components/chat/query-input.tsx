"use client";

import { useRef } from "react";
import { Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface Props {
  onSend: (text: string) => void;
  isLoading: boolean;
}

export function QueryInput({ onSend, isLoading }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const value = textareaRef.current?.value.trim();
    if (!value || isLoading) return;
    onSend(value);
    if (textareaRef.current) {
      textareaRef.current.value = "";
      // Reset height after clearing
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const el = e.currentTarget;
    // Auto-resize: shrink to "auto" then set to scrollHeight
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  return (
    <div className="flex items-end gap-2">
      <Textarea
        ref={textareaRef}
        rows={1}
        placeholder={
          isLoading ? "Thinking…" : "Ask about your e-commerce operations…"
        }
        disabled={isLoading}
        onKeyDown={handleKeyDown}
        onChange={handleInput}
        className={cn(
          "min-h-[2.5rem] flex-1 resize-none overflow-hidden rounded-lg border border-border py-2.5 transition-all placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20",
          isLoading && "cursor-not-allowed opacity-60",
        )}
      />
      <Button
        size="icon"
        disabled={isLoading}
        onClick={handleSend}
        aria-label="Send message"
        className="size-10 shrink-0 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {isLoading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Send className="size-4" />
        )}
      </Button>
    </div>
  );
}
