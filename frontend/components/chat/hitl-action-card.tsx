"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, CheckCircle, Clock, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getAction } from "@/lib/api";
import type {
  ActionExecutionResult,
  ActionType,
  PendingAction,
  PendingApprovalMessage,
} from "@/lib/types";

const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  restock: "Restock",
  run_discount: "Run Discount",
  pause_campaign: "Pause Campaign",
  resume_campaign: "Resume Campaign",
  create_support_ticket: "Create Support Ticket",
};

function ResultBadge({ result }: { result: ActionExecutionResult }) {
  const isExecuted = result.status === "executed";
  return (
    <div className="flex items-center gap-2">
      {isExecuted ? (
        <CheckCircle className="size-4 text-emerald-500" />
      ) : (
        <XCircle className="size-4 text-destructive" />
      )}
      <span
        className={`text-xs font-medium ${
          isExecuted
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-destructive"
        }`}
      >
        {result.message}
      </span>
    </div>
  );
}

function ActionRow({
  action,
  result,
  onApprove,
  isHistorical,
}: {
  action: PendingAction;
  result?: ActionExecutionResult;
  onApprove: (actionId: string, approved: boolean) => Promise<void>;
  isHistorical?: boolean;
}) {
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);

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
            {ACTION_TYPE_LABELS[action.action_type]}
          </Badge>
          <p className="text-sm font-medium text-foreground">
            {action.description}
          </p>
        </div>

        {isHistorical ? (
          <span className="rounded-full border border-border px-2 py-0.5 text-[0.65rem] text-muted-foreground">
            Historical
          </span>
        ) : result ? (
          <ResultBadge result={result} />
        ) : (
          <div className="flex shrink-0 gap-1.5">
            <Button
              size="sm"
              variant="outline"
              disabled={pending !== null}
              onClick={() => handleClick(true)}
              className="h-7 font-medium text-emerald-700 border-emerald-300 hover:bg-emerald-50 hover:border-emerald-400 dark:text-emerald-400 dark:border-emerald-800 dark:hover:bg-emerald-950 disabled:opacity-50"
            >
              {pending === "approve" ? (
                <Clock className="mr-1 size-3 animate-spin" />
              ) : (
                <CheckCircle className="mr-1 size-3" />
              )}
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending !== null}
              onClick={() => handleClick(false)}
              className="h-7 font-medium text-destructive border-destructive/30 hover:bg-destructive/5 hover:border-destructive/50 disabled:opacity-50"
            >
              {pending === "reject" ? (
                <Clock className="mr-1 size-3 animate-spin" />
              ) : (
                <XCircle className="mr-1 size-3" />
              )}
              Reject
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  message: PendingApprovalMessage;
  onApprove: (
    messageId: string,
    actionId: string,
    approved: boolean,
  ) => Promise<void>;
}

export function HitlActionCard({ message, onApprove }: Props) {
  // Track resolutions detected by polling (for actions approved/rejected externally).
  const [polledResolved, setPolledResolved] = useState<
    Record<string, ActionExecutionResult>
  >({});

  // Merge parent-tracked resolutions (in-chat) with polling-detected ones.
  const allResolved = { ...polledResolved, ...message.resolvedActions };
  const pendingCount = message.actions.filter((a) => !allResolved[a.id]).length;

  // Poll backend for action statuses when there are still unresolved actions.
  // Only runs for non-historical cards (historical cards are read-only anyway).
  const pendingKey = message.actions
    .filter((a) => !allResolved[a.id])
    .map((a) => a.id)
    .join(",");
  const pendingKeyRef = useRef(pendingKey);
  pendingKeyRef.current = pendingKey;

  useEffect(() => {
    if (message.is_historical || !pendingKey) return;

    const poll = async () => {
      const ids = pendingKeyRef.current.split(",").filter(Boolean);
      for (const actionId of ids) {
        try {
          const fetched = await getAction(actionId);
          if (fetched.status !== "pending_approval") {
            setPolledResolved((prev) => ({
              ...prev,
              [actionId]: {
                action_type: fetched.action_type,
                status: fetched.status,
                message:
                  fetched.status === "rejected"
                    ? "Action rejected."
                    : "Action approved.",
                executed_at: fetched.executed_at ?? null,
              },
            }));
          }
        } catch {
          // Ignore — polling is best-effort
        }
      }
    };

    poll();
    const interval = setInterval(poll, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingKey, message.is_historical]);

  return (
    <div className="flex w-full max-w-3xl items-end gap-2">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Bot className="size-4" />
      </div>
      <Card className="flex-1 border-border shadow-sm transition-shadow duration-200 hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Clock className="size-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">
              Actions Awaiting Your Approval
            </span>
            {pendingCount > 0 && (
              <Badge variant="secondary" className="ml-auto text-[0.65rem]">
                {pendingCount} pending
              </Badge>
            )}
          </div>
        </CardHeader>

        <Separator />

        <CardContent className="flex flex-col gap-2 pt-4">
          {message.actions.map((action, i) => (
            <ActionRow
              key={action.id ?? `${action.action_type}-${i}`}
              action={action}
              result={allResolved[action.id]}
              onApprove={(actionId, approved) =>
                onApprove(message.id, actionId, approved)
              }
              isHistorical={message.is_historical}
            />
          ))}
        </CardContent>

        <CardFooter className="pt-2 text-[0.7rem] font-medium text-muted-foreground">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </CardFooter>
      </Card>
    </div>
  );
}
