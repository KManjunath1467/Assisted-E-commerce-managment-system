"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

  // Synchronous guard to prevent double-submission (useRef, not state).
  const sendingRef = useRef(false);
  // AbortController for the current SSE stream — aborted on unmount.
  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight stream on unmount.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // ─── Send a user message ──────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (text: string, timeRange?: TimeRange | null) => {
      if (sendingRef.current || !text.trim()) return;
      sendingRef.current = true;

      // Abort any previous stream still in flight.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

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
        timestamp: nowIso(),
      };
      setMessages((prev) => [...prev, userMsg, streamMsg]);
      setIsLoading(true);

      try {
        for await (const event of postQueryStream(
          text.trim(),
          threadIdRef.current,
          timeRange,
          controller.signal,
        )) {
          if (event.event === "node_complete") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamId && m.type === "streaming"
                  ? { ...m, currentNode: event.data.node }
                  : m,
              ),
            );
          } else if (event.event === "complete") {
            const response = event.data;
            threadIdRef.current = response.thread_id;
            setActiveThreadId(response.thread_id);
            if (!response.report) return;
            const reportMsg: ReportMessage = {
              id: newId(),
              type: "report",
              report: response.report,
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
        // Ignore abort errors — they're expected on unmount / new message.
        if (err instanceof DOMException && err.name === "AbortError") return;
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
        sendingRef.current = false;
      }
    },
    [],
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
    abortRef.current?.abort();
    setMessages([]);
    threadIdRef.current = null;
    setActiveThreadId(null);
    sendingRef.current = false;
    setIsLoading(false);
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
    activeThreadId,
    sendMessage,
    handleApprove,
    startNewChat,
    loadThread,
  };
}
