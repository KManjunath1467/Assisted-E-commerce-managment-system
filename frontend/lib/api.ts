import type {
  ActionExecutionResult,
  ActionApprovalPayload,
  Incident,
  PendingAction,
  QueryRequest,
  QueryResponse,
  ThreadMessageItem,
  ThreadSummary,
  TimeRange,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    let detail: string;
    try {
      const json = await res.json();
      detail = json?.detail ?? JSON.stringify(json);
    } catch {
      detail = await res.text();
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }

  return res.json() as Promise<T>;
}

// ─── SSE event types ──────────────────────────────────────────────────────

export type StreamEvent =
  | { event: "node_complete"; data: { node: string } }
  | { event: "token"; data: { content: string } }
  | { event: "complete"; data: QueryResponse }
  | { event: "pending_approval"; data: QueryResponse }
  | { event: "error"; data: { detail: string } };

/**
 * POST /api/v1/query/stream
 * Opens an SSE connection and yields parsed events as they arrive.
 */
export async function* postQueryStream(
  query: string,
  threadId?: string | null,
  timeRange?: TimeRange | null,
): AsyncGenerator<StreamEvent> {
  const body: QueryRequest = {
    query,
    thread_id: threadId ?? null,
    time_range: timeRange ?? null,
  };

  const res = await fetch(`${BASE}/api/v1/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail: string;
    try {
      const json = await res.json();
      detail = json?.detail ?? JSON.stringify(json);
    } catch {
      detail = await res.text();
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep the last (potentially incomplete) line in the buffer.
    buffer = lines.pop() ?? "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        try {
          const data = JSON.parse(line.slice(6));
          yield { event: currentEvent, data } as StreamEvent;
        } catch {
          // skip malformed JSON
        }
        currentEvent = "";
      }
    }
  }
}

/**
 * POST /api/v1/query (non-streaming fallback)
 * Submits a user query to the multi-agent graph.
 * Prefer postQueryStream() for real-time progress updates.
 */
export function postQuery(
  query: string,
  threadId?: string | null,
  timeRange?: TimeRange | null,
): Promise<QueryResponse> {
  const body: QueryRequest = {
    query,
    thread_id: threadId ?? null,
    time_range: timeRange ?? null,
  };
  return apiFetch<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * GET /api/v1/actions/{actionId}
 * Returns a single action with its current status (any status, not just pending).
 * Used by the HITL card to poll for externally resolved actions.
 */
export function getAction(actionId: string): Promise<PendingAction> {
  return apiFetch<PendingAction>(`/api/v1/actions/${actionId}`);
}

/**
 * GET /api/v1/actions
 * Returns all actions regardless of status, most recent first.
 */
export function getAllActions(): Promise<PendingAction[]> {
  return apiFetch<PendingAction[]>("/api/v1/actions");
}

/**
 * GET /api/v1/actions/pending
 * Returns all actions currently awaiting human approval.
 */
export function getPendingActions(): Promise<PendingAction[]> {
  return apiFetch<PendingAction[]>("/api/v1/actions/pending");
}

/**
 * POST /api/v1/actions/{actionId}/approve
 * Approves or rejects a pending action and resumes the LangGraph thread.
 */
export function approveAction(
  actionId: string,
  approved: boolean,
  threadId: string | null,
  notes?: string | null,
): Promise<ActionExecutionResult> {
  const body: ActionApprovalPayload = {
    approved,
    approved_by: null,
    notes: notes ?? null,
    thread_id: threadId,
  };
  return apiFetch<ActionExecutionResult>(
    `/api/v1/actions/${actionId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

/**
 * GET /api/v1/threads
 * Returns all threads ordered by most recently updated.
 */
export function getThreads(): Promise<ThreadSummary[]> {
  return apiFetch<ThreadSummary[]>("/api/v1/threads");
}

/**
 * GET /api/v1/threads/{threadId}/history
 * Returns all messages for a thread in chronological order.
 */
export async function getThreadHistory(
  threadId: string,
): Promise<ThreadMessageItem[]> {
  const data = await apiFetch<{
    thread_id: string;
    messages: ThreadMessageItem[];
  }>(`/api/v1/threads/${threadId}/history`);
  return data.messages;
}

/**
 * GET /api/v1/incidents
 * Returns all incidents ordered by most recent.
 */
export function getIncidents(): Promise<Incident[]> {
  return apiFetch<Incident[]>("/api/v1/incidents");
}

/**
 * PATCH /api/v1/incidents/{incidentId}/resolve
 * Marks an incident as resolved and rejects any pending actions.
 */
export function resolveIncident(
  incidentId: string,
  resolutionSummary?: string | null,
): Promise<Incident> {
  return apiFetch<Incident>(`/api/v1/incidents/${incidentId}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ resolution_summary: resolutionSummary ?? null }),
  });
}
