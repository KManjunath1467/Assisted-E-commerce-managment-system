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
    <div className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
      <span className="flex items-center gap-[3px]">
        {[0, 160, 320].map((delay) => (
          <span
            key={delay}
            className="size-1.5 rounded-full bg-primary animate-bounce"
            style={{ animationDelay: `${delay}ms`, animationDuration: "1s" }}
          />
        ))}
      </span>
      <span key={label} className="animate-in fade-in slide-in-from-bottom-1 duration-300">
        {label}…
      </span>
    </div>
  );
}
