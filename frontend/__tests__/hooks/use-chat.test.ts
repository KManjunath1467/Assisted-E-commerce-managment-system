import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// --- Mocks ----------------------------------------------------------------

const mockApproveAction = vi.fn();
const mockPostQueryStream = vi.fn();

vi.mock("@/lib/api", () => ({
  approveAction: (...args: unknown[]) => mockApproveAction(...args),
  postQueryStream: (...args: unknown[]) => mockPostQueryStream(...args),
}));

// useChat uses crypto.randomUUID — provide a stable stub.
let uuidCounter = 0;
vi.stubGlobal("crypto", {
  randomUUID: () => `test-uuid-${++uuidCounter}`,
});

// Import after mocks are set up.
const { useChat } = await import("@/hooks/use-chat");

// Helper: build an async generator from a list of events.
async function* makeStream(events: object[]) {
  for (const ev of events) yield ev;
}

// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  uuidCounter = 0;
});

// ---------------------------------------------------------------------------

describe("useChat — sendMessage", () => {
  it("adds user bubble + resolves to report on complete event", async () => {
    const report = {
      query: "test",
      thread_id: "t1",
      incident_id: null,
      recommendations: [],
      summary: "All good",
    };

    mockPostQueryStream.mockImplementation(() =>
      makeStream([
        { event: "node_complete", data: { node: "sales_agent" } },
        { event: "token", data: { content: "All " } },
        { event: "token", data: { content: "good" } },
        { event: "complete", data: { status: "complete", thread_id: "t1", report } },
      ]),
    );

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("test query");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const msgs = result.current.messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].type).toBe("user");
    expect(msgs[1].type).toBe("report");
    expect(result.current.activeThreadId).toBe("t1");
  });

  it("replaces placeholder with pending_approval on interrupt", async () => {
    const pendingAction = {
      id: "act-1",
      incident_id: "inc-1",
      action_type: "restock",
      description: "Restock item",
      parameters: {},
      created_at: new Date().toISOString(),
      executed_at: null,
      thread_id: "t2",
      status: "pending_approval",
    };

    mockPostQueryStream.mockImplementation(() =>
      makeStream([
        {
          event: "pending_approval",
          data: { status: "pending_approval", thread_id: "t2", report: null, pending_actions: [pendingAction] },
        },
      ]),
    );

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("restock request");
    });

    await waitFor(() => expect(result.current.messages[1]?.type).toBe("pending_approval"));

    const msg = result.current.messages[1];
    if (msg.type === "pending_approval") {
      expect(msg.actions).toHaveLength(1);
      expect(msg.thread_id).toBe("t2");
    }
  });

  it("shows error message when stream throws", async () => {
    mockPostQueryStream.mockImplementation(async function* () {
      throw new Error("Network failure");
      yield; // satisfy TS generator signature
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("bad query");
    });

    await waitFor(() => expect(result.current.messages[1]?.type).toBe("error"));

    const msg = result.current.messages[1];
    if (msg.type === "error") expect(msg.text).toContain("Network failure");
    expect(result.current.isLoading).toBe(false);
  });

  it("ignores whitespace-only input", async () => {
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("   ");
    });

    expect(mockPostQueryStream).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it("prevents double-submission via synchronous ref guard", async () => {
    // Slow stream so the second call arrives while first is in-flight.
    mockPostQueryStream.mockImplementation(async function* () {
      await new Promise((r) => setTimeout(r, 10));
      yield { event: "complete", data: { status: "complete", thread_id: "t3", report: { query: "q", thread_id: "t3", incident_id: null, recommendations: [], summary: "ok" } } };
    });

    const { result } = renderHook(() => useChat());

    act(() => {
      void result.current.sendMessage("first");
      void result.current.sendMessage("second"); // should be blocked
    });

    await waitFor(() => !result.current.isLoading);
    expect(mockPostQueryStream).toHaveBeenCalledTimes(1);
  });

  it("shows error SSE event as error message", async () => {
    mockPostQueryStream.mockImplementation(() =>
      makeStream([{ event: "error", data: { detail: "Agent crashed" } }]),
    );

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("crash test");
    });

    await waitFor(() => expect(result.current.messages[1]?.type).toBe("error"));
    const msg = result.current.messages[1];
    if (msg.type === "error") expect(msg.text).toBe("Agent crashed");
  });
});

// ---------------------------------------------------------------------------

describe("useChat — handleApprove", () => {
  it("stores execution result in resolvedActions", async () => {
    mockPostQueryStream.mockImplementation(() =>
      makeStream([
        {
          event: "pending_approval",
          data: {
            status: "pending_approval",
            thread_id: "t4",
            report: null,
            pending_actions: [
              { id: "act-1", incident_id: "i1", action_type: "restock", description: "Restock", parameters: {}, created_at: new Date().toISOString(), executed_at: null, thread_id: "t4", status: "pending_approval" },
            ],
          },
        },
      ]),
    );

    mockApproveAction.mockResolvedValue({
      action_type: "restock",
      status: "executed",
      message: "Done",
      executed_at: new Date().toISOString(),
    });

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("trigger HITL");
    });

    const messageId = result.current.messages[1].id;

    await act(async () => {
      await result.current.handleApprove(messageId, "act-1", true, null);
    });

    const msg = result.current.messages[1];
    expect(msg.type).toBe("pending_approval");
    if (msg.type === "pending_approval") {
      expect(msg.resolvedActions["act-1"].status).toBe("executed");
    }
  });

  it("re-throws when approveAction fails", async () => {
    mockApproveAction.mockRejectedValue(new Error("Server error"));
    const { result } = renderHook(() => useChat());

    await expect(
      act(async () => {
        await result.current.handleApprove("msg-id", "act-1", true, null);
      }),
    ).rejects.toThrow("Server error");
  });
});

// ---------------------------------------------------------------------------

describe("useChat — helpers", () => {
  it("startNewChat resets all state", async () => {
    mockPostQueryStream.mockImplementation(() =>
      makeStream([
        { event: "complete", data: { status: "complete", thread_id: "t5", report: { query: "q", thread_id: "t5", incident_id: null, recommendations: [], summary: "ok" } } },
      ]),
    );

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage("hello");
    });
    expect(result.current.messages.length).toBeGreaterThan(0);

    act(() => result.current.startNewChat());

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.activeThreadId).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("loadThread populates messages and activeThreadId", () => {
    const { result } = renderHook(() => useChat());
    const msgs = [
      { id: "m1", type: "user" as const, text: "hello", timestamp: new Date().toISOString() },
    ];

    act(() => result.current.loadThread("thread-xyz", msgs));

    expect(result.current.activeThreadId).toBe("thread-xyz");
    expect(result.current.messages).toEqual(msgs);
  });
});
