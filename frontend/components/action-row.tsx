"use client";

import { useState } from "react";
import { CheckCircle, Clock, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ActionExecutionResult, ActionType, PendingAction } from "@/lib/types";

export const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  restock: "Restock",
  run_discount: "Run Discount",
  pause_campaign: "Pause Campaign",
  resume_campaign: "Resume Campaign",
  create_support_ticket: "Create Support Ticket",
};

const STATUS_COLORS: Record<string, string> = {
  pending_approval: "text-warning",
  executed: "text-success",
  approved: "text-success",
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
    return <CheckCircle className="size-3.5 text-success" />;
  if (status === "rejected")
    return <XCircle className="size-3.5 text-destructive" />;
  return <Clock className="size-3.5 text-warning" />;
}

function ResultBadge({ result }: { result: ActionExecutionResult }) {
  const isExecuted = result.status === "executed";
  return (
    <div className="flex items-center gap-2">
      {isExecuted ? (
        <CheckCircle className="size-4 text-success" />
      ) : (
        <XCircle className="size-4 text-destructive" />
      )}
      <span
        className={`text-xs font-medium ${
          isExecuted ? "text-success" : "text-destructive"
        }`}
      >
        {result.message}
      </span>
    </div>
  );
}

function ApproveRejectButtons({
  pending,
  onApprove,
  onReject,
}: {
  pending: "approve" | "reject" | null;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="flex shrink-0 gap-1.5">
      <Button
        size="sm"
        variant="outline"
        disabled={pending !== null}
        onClick={onApprove}
        className="h-7 font-medium text-success border-success/30 hover:bg-success/10 hover:border-success/40 disabled:opacity-50"
      >
        {pending === "approve" ? (
          <Loader2 className="mr-1 size-3 animate-spin" />
        ) : (
          <CheckCircle className="mr-1 size-3" />
        )}
        Approve
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={pending !== null}
        onClick={onReject}
        className="h-7 font-medium text-destructive border-destructive/30 hover:bg-destructive/5 hover:border-destructive/50 disabled:opacity-50"
      >
        {pending === "reject" ? (
          <Loader2 className="mr-1 size-3 animate-spin" />
        ) : (
          <XCircle className="mr-1 size-3" />
        )}
        Reject
      </Button>
    </div>
  );
}

interface ActionRowProps {
  action: PendingAction;
  result?: ActionExecutionResult;
  onApprove: (actionId: string, approved: boolean) => Promise<void>;
  isHistorical?: boolean;
  /** When true, always shows status icon + label in the top-right (actions page style).
   *  When false (default), shows approve/reject inline or ResultBadge (HITL card style). */
  showStatus?: boolean;
}

export function ActionRow({
  action,
  result,
  onApprove,
  isHistorical = false,
  showStatus = false,
}: ActionRowProps) {
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);
  const isPending = action.status === "pending_approval";

  async function handleClick(approved: boolean) {
    setPending(approved ? "approve" : "reject");
    try {
      await onApprove(action.id, approved);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3 shadow-sm">
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
          {showStatus ? (
            <>
              <ActionStatusIcon status={action.status} />
              <span
                className={`text-xs font-medium ${STATUS_COLORS[action.status] ?? ""}`}
              >
                {STATUS_LABELS[action.status] ??
                  action.status.replace(/_/g, " ")}
              </span>
            </>
          ) : isHistorical ? (
            <span className="rounded-full border border-border px-2 py-0.5 text-[0.65rem] text-muted-foreground">
              Historical
            </span>
          ) : result ? (
            <ResultBadge result={result} />
          ) : (
            // HITL pending: inline buttons in top-right
            <ApproveRejectButtons
              pending={pending}
              onApprove={() => handleClick(true)}
              onReject={() => handleClick(false)}
            />
          )}
        </div>
      </div>

      {/* Actions page: approve/reject below the top row when pending */}
      {showStatus && isPending && (
        <ApproveRejectButtons
          pending={pending}
          onApprove={() => handleClick(true)}
          onReject={() => handleClick(false)}
        />
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
