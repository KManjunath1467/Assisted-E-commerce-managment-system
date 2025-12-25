"use client";

import { useCallback, useRef, useState } from "react";
import { approveAction, postQueryStream } from "@/lib/api";
import type {
  ActionExecutionResult,
  ChatMessage,
  ErrorMessage,
  PendingApprovalMessage,
  ReportMessage,
  StreamingMessage,
  TimeRange,
  UserMessage,
} from "@/lib/types";

function newId(): string {
  return crypto.randomUUID();
}

function nowIso(): string {
  return new Date().toISOString();
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const threadIdRef = useRef<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  // ─── Send a user message ──────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (text: string, timeRange?: TimeRange | null) => {
      if (isLoading || !text.trim()) return;

      // Append the user bubble immediately.
      const userMsg: UserMessage = {
        id: newId(),
        type: "user",
        text: text.trim(),
        timestamp: nowIso(),
      };

      // Insert a streaming-progress placeholder.
      const streamId = newId();
      const streamMsg: StreamingMessage = {
        id: streamId,
        type: "streaming",
        currentNode: null,
        streamedText: "",
        timestamp: nowIso(),
      };
      setMessages((prev) => [...prev, userMsg, streamMsg]);
      setIsLoading(true);

      try {
        for await (const event of postQueryStream(
          text.trim(),
          threadIdRef.current,
          timeRange,
        )) {
          if (event.event === "node_complete") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamId && m.type === "streaming"
                  ? { ...m, currentNode: event.data.node }
                  : m,
              ),
            );
          } else if (event.event === "token") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamId && m.type === "streaming"
                  ? {
                      ...m,
                      streamedText: m.streamedText + event.data.content,
                      currentNode: null,
                    }
                  : m,
              ),
            );
          } else if (event.event === "complete") {
            const response = event.data;
            threadIdRef.current = response.thread_id;
            setActiveThreadId(response.thread_id);
            const reportMsg: ReportMessage = {
              id: newId(),
              type: "report",
              report: response.report!,
              thread_id: response.thread_id,
              timestamp: nowIso(),
            };
            // Replace the streaming placeholder with the final report.
            setMessages((prev) =>
              prev.map((m) => (m.id === streamId ? reportMsg : m)),
            );
          } else if (event.event === "pending_approval") {
            const response = event.data;
            threadIdRef.current = response.thread_id;
            setActiveThreadId(response.thread_id);
            const pendingMsg: PendingApprovalMessage = {
              id: newId(),
              type: "pending_approval",
              actions: response.pending_actions ?? [],
              thread_id: response.thread_id,
              timestamp: nowIso(),
              resolvedActions: {},
            };
            setMessages((prev) =>
              prev.map((m) => (m.id === streamId ? pendingMsg : m)),
            );
          } else if (event.event === "error") {
            const errorMsg: ErrorMessage = {
              id: newId(),
              type: "error",
              text: event.data.detail,
              timestamp: nowIso(),
            };
            setMessages((prev) =>
              prev.map((m) => (m.id === streamId ? errorMsg : m)),
            );
          }
        }
      } catch (err) {
        const errorMsg: ErrorMessage = {
          id: newId(),
          type: "error",
          text:
            err instanceof Error
              ? err.message
              : "An unexpected error occurred.",
          timestamp: nowIso(),
        };
        // Replace the streaming placeholder with the error.
        setMessages((prev) =>
          prev.map((m) => (m.id === streamId ? errorMsg : m)),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading],
  );

  // ─── Approve or reject a pending action ──────────────────────────────────

  const handleApprove = useCallback(
    async (
      messageId: string,
      actionId: string,
      approved: boolean,
      notes?: string | null,
    ): Promise<void> => {
      // Find the message that owns this action to extract its thread_id.
      // Uses messagesRef to avoid re-creating this callback on every message change.
      const ownerMessage = messagesRef.current.find((m) => m.id === messageId);
      const threadId =
        ownerMessage && ownerMessage.type === "pending_approval"
          ? ownerMessage.thread_id
          : threadIdRef.current;

      let result: ActionExecutionResult;
      try {
        result = await approveAction(actionId, approved, threadId, notes);
      } catch (err) {
        // Re-throw so the HITL card resets its button state and the action
        // stays retryable. Don't fabricate a fake business result.
        console.error("Action approval failed:", err);
        throw err;
      }

      // Update only the specific pending_approval message — insert resolved entry.
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== messageId || m.type !== "pending_approval") return m;
          return {
            ...m,
            resolvedActions: {
              ...m.resolvedActions,
              [actionId]: result,
            },
          };
        }),
      );
    },
    [],
  );

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const startNewChat = useCallback(() => {
    setMessages([]);
    threadIdRef.current = null;
    setActiveThreadId(null);
  }, []);

  const loadThread = useCallback(
    (threadId: string, threadMessages: ChatMessage[]) => {
      threadIdRef.current = threadId;
      setActiveThreadId(threadId);
      setMessages(threadMessages);
    },
    [],
  );

  return {
    messages,
    isLoading,
    threadId: threadIdRef.current,
    activeThreadId,
    sendMessage,
    handleApprove,
    startNewChat,
    loadThread,
  };
}
