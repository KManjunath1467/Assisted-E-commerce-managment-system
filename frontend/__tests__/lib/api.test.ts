import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock global fetch.
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Import after mocking fetch.
import { approveAction, getAction, getPendingActions } from "@/lib/api";

describe("api client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("approveAction", () => {
    it("sends correct payload with thread_id", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            action_type: "restock",
            status: "executed",
            message: "Done",
            executed_at: "2025-01-01T00:00:00Z",
          }),
      });

      const result = await approveAction("action-123", true, "thread-456");
      expect(result.status).toBe("executed");

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain("/api/v1/actions/action-123/approve");
      const body = JSON.parse(init.body);
      expect(body.approved).toBe(true);
      expect(body.thread_id).toBe("thread-456");
    });

    it("sends null thread_id when none provided", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            action_type: "restock",
            status: "rejected",
            message: "Rejected",
            executed_at: null,
          }),
      });

      await approveAction("action-123", false, null);

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.thread_id).toBeNull();
    });

    it("throws on non-ok response", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: "Action not found." }),
      });

      await expect(approveAction("bad-id", true, null)).rejects.toThrow(
        "API 404",
      );
    });
  });

  describe("getAction", () => {
    it("fetches and returns a single action", async () => {
      const action = {
        id: "a1",
        incident_id: "i1",
        action_type: "restock",
        description: "Restock",
        status: "pending_approval",
        created_at: "2025-01-01",
        executed_at: null,
        thread_id: "t1",
      };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(action),
      });

      const result = await getAction("a1");
      expect(result.thread_id).toBe("t1");
    });
  });

  describe("getPendingActions", () => {
    it("returns array of pending actions", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      const result = await getPendingActions();
      expect(result).toEqual([]);
    });
  });
});
