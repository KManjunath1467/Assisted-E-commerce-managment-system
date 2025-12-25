import { Loader2 } from "lucide-react";

const NODE_LABELS: Record<string, string> = {
  router: "Routing query",
  orchestrator: "Planning analysis",
  sales: "Analyzing sales",
  inventory: "Checking inventory",
  marketing: "Reviewing campaigns",
  customer_support: "Reviewing support",
  aggregator: "Aggregating findings",
  reflector: "Reflecting on analysis",
  hitl: "Preparing actions",
  final_response: "Writing report",
};

export function StreamingProgress({
  currentNode,
}: {
  currentNode: string | null;
}) {
  const label = currentNode
    ? (NODE_LABELS[currentNode] ?? currentNode)
    : "Thinking";

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground py-1">
      <Loader2 className="size-3.5 animate-spin" />
      <span>{label}…</span>
    </div>
  );
}
