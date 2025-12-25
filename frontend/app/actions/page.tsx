"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  MessageSquare,
  RefreshCw,
  XCircle,
  Zap,
} from "lucide-react";
import { approveAction, getAllActions } from "@/lib/api";
import type { PendingAction } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

const ACTION_TYPE_LABELS: Record<string, string> = {
  restock: "Restock",
  run_discount: "Run Discount",
  pause_campaign: "Pause Campaign",
  resume_campaign: "Resume Campaign",
  create_support_ticket: "Create Support Ticket",
};

const STATUS_COLORS: Record<string, string> = {
  pending_approval: "text-amber-600 dark:text-amber-400",
  executed: "text-emerald-600 dark:text-emerald-400",
  approved: "text-emerald-600 dark:text-emerald-400",
  rejected: "text-destructive",
};

const STATUS_LABELS: Record<string, string> = {
  pending_approval: "Pending",
  executed: "Approved",
  approved: "Approved",
  rejected: "Rejected",
};

function ActionStatusIcon({ status }: { status: string }) {
  if (status === "executed" || status === "approved")
    return <CheckCircle className="size-3.5 text-emerald-500" />;
  if (status === "rejected")
    return <XCircle className="size-3.5 text-destructive" />;
  return <Clock className="size-3.5 text-amber-500" />;
}

function ActionRow({
  action,
  onAction,
}: {
  action: PendingAction;
  onAction: (actionId: string, approved: boolean) => Promise<void>;
}) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const isPending = action.status === "pending_approval";

  async function handle(approved: boolean) {
    setBusy(approved ? "approve" : "reject");
    try {
      await onAction(action.id, approved);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Badge variant="outline" className="w-fit text-[0.65rem] font-bold">
            {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
          </Badge>
          <p className="text-sm font-medium text-foreground">
            {action.description}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <ActionStatusIcon status={action.status} />
          <span
            className={`text-xs font-medium ${STATUS_COLORS[action.status] ?? ""}`}
          >
            {STATUS_LABELS[action.status] ?? action.status.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {isPending && (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="outline"
            disabled={busy !== null}
            onClick={() => handle(true)}
            className="h-7 font-medium text-emerald-700 border-emerald-300 hover:bg-emerald-50 hover:border-emerald-400 dark:text-emerald-400 dark:border-emerald-800 dark:hover:bg-emerald-950 disabled:opacity-50"
          >
            {busy === "approve" ? (
              <Clock className="mr-1 size-3 animate-spin" />
            ) : (
              <CheckCircle className="mr-1 size-3" />
            )}
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy !== null}
            onClick={() => handle(false)}
            className="h-7 font-medium text-destructive border-destructive/30 hover:bg-destructive/5 hover:border-destructive/50 disabled:opacity-50"
          >
            {busy === "reject" ? (
              <Clock className="mr-1 size-3 animate-spin" />
            ) : (
              <XCircle className="mr-1 size-3" />
            )}
            Reject
          </Button>
        </div>
      )}

      {action.executed_at && (
        <p className="text-[0.65rem] text-muted-foreground">
          Approved{" "}
          {new Date(action.executed_at).toLocaleString([], {
            dateStyle: "medium",
            timeStyle: "short",
          })}
        </p>
      )}
    </div>
  );
}

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
      // 409 means the action was already approved/rejected (e.g. from chat).
      // Refresh the full list to get the current state from the server.
      await fetchData();
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
      {/* Header */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-background/90 px-6 py-3 backdrop-blur-sm shadow-sm">
        <Zap className="size-5 text-primary" />
        <span className="text-sm font-semibold text-foreground">Actions</span>
        {pendingCount > 0 && (
          <Badge variant="secondary" className="text-[0.65rem]">
            {pendingCount} pending
          </Badge>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Link href="/">
            <Button variant="ghost" size="sm" className="text-xs gap-1.5">
              <MessageSquare className="size-3.5" />
              Chat
            </Button>
          </Link>
          <Link href="/incidents">
            <Button variant="ghost" size="sm" className="text-xs gap-1.5">
              <AlertCircle className="size-3.5" />
              Incidents
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
            className="text-xs gap-1.5"
          >
            <RefreshCw
              className={`size-3.5 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <ThemeToggle />
        </div>
      </header>

      {/* Tabs */}
      <div className="shrink-0 border-b border-border bg-background px-6">
        <div className="mx-auto flex max-w-3xl gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-medium transition-colors focus-visible:outline-none ${
                activeTab === tab.key
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
              <span
                className={`rounded-full px-1.5 py-0.5 text-[0.6rem] font-semibold ${
                  activeTab === tab.key
                    ? tab.key === "pending"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                      : "bg-muted text-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {isLoading && actions.length === 0 && (
            <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
              <RefreshCw className="mr-2 size-4 animate-spin" />
              Loading actions…
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {!isLoading && !error && filteredActions.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <CheckCircle className="size-10 text-emerald-500" />
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
              onAction={handleAction}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
