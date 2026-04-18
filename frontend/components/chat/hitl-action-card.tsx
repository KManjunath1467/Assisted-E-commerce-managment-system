"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ActionRow } from "@/components/action-row";
import { getAction } from "@/lib/api";
import type {
  ActionExecutionResult,
  PendingApprovalMessage,
} from "@/lib/types";

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
  const pendingKey = message.actions
    .filter((a) => !allResolved[a.id])
    .map((a) => a.id)
    .join(",");
  const pendingKeyRef = useRef(pendingKey);
  pendingKeyRef.current = pendingKey;

  useEffect(() => {
    if (message.is_historical || !pendingKey) return;

    const controller = new AbortController();
    let polling = false;

    const poll = async () => {
      if (polling || controller.signal.aborted) return;
      polling = true;
      try {
        const ids = pendingKeyRef.current.split(",").filter(Boolean);
        const results = await Promise.all(
          ids.map((id) =>
            getAction(id, controller.signal).catch(() => null),
          ),
        );
        for (const fetched of results) {
          if (fetched && fetched.status !== "pending_approval") {
            setPolledResolved((prev) => ({
              ...prev,
              [fetched.id]: {
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
        }
      } finally {
        polling = false;
      }
    };

    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [pendingKey, message.is_historical]);

  return (
    <div className="flex w-full max-w-3xl items-start gap-2">
      <div className="mb-5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
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
