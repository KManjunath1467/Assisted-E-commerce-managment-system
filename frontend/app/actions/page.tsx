"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, Zap } from "lucide-react";
import { approveAction, getAllActions } from "@/lib/api";
import type { PendingAction } from "@/lib/types";
import { ActionRow } from "@/components/action-row";
import { FilterTabs } from "@/components/filter-tabs";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";

type ActionFilter = "pending" | "all";

export default function ActionsPage() {
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActionFilter>("pending");

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getAllActions();
      setActions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load actions.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Poll for status changes every 5 seconds so approvals from chat
    // (or other tabs) are reflected without a manual refresh.
    const interval = setInterval(async () => {
      // Skip poll when tab is hidden — no need to burn requests nobody sees.
      if (document.visibilityState === "hidden") return;
      try {
        const data = await getAllActions();
        setActions(data);
      } catch {
        // Silently ignore polling errors — the user can still manually refresh.
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  async function handleAction(actionId: string, approved: boolean) {
    const action = actions.find((a) => a.id === actionId);
    try {
      const result = await approveAction(
        actionId,
        approved,
        action?.thread_id ?? null,
      );
      setActions((prev) =>
        prev.map((a) =>
          a.id === actionId
            ? { ...a, status: result.status, executed_at: result.executed_at }
            : a,
        ),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409")) {
        // Action was already approved/rejected (e.g. from chat). Refresh.
        await fetchData();
      } else {
        setError(`Action failed: ${msg}`);
      }
    }
  }

  const pendingCount = actions.filter(
    (a) => a.status === "pending_approval",
  ).length;

  const filteredActions =
    activeTab === "pending"
      ? actions.filter((a) => a.status === "pending_approval")
      : actions;

  const tabs: { key: ActionFilter; label: string; count: number }[] = [
    { key: "pending", label: "Pending", count: pendingCount },
    { key: "all", label: "All", count: actions.length },
  ];

  return (
    <div className="flex h-screen flex-col bg-background">
      <PageHeader
        page="actions"
        icon={Zap}
        title="Actions"
        badgeText={pendingCount > 0 ? `${pendingCount} pending` : undefined}
        isLoading={isLoading}
        onRefresh={fetchData}
      />
      <FilterTabs
        tabs={tabs}
        activeTab={activeTab}
        warningKey="pending"
        onChange={setActiveTab}
      />

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {isLoading && actions.length === 0 && (
            <>
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {!isLoading && !error && filteredActions.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <CheckCircle className="size-10 text-success" />
              <p className="text-sm font-medium text-foreground">
                {activeTab === "pending"
                  ? "No pending actions"
                  : "No actions found"}
              </p>
              <p className="text-xs text-muted-foreground">
                {activeTab === "pending"
                  ? "Nothing awaiting approval."
                  : "Actions appear here once incidents are created."}
              </p>
            </div>
          )}

          {filteredActions.map((action) => (
            <ActionRow
              key={action.id}
              action={action}
              onApprove={handleAction}
              showStatus
            />
          ))}
        </div>
      </main>
    </div>
  );
}
