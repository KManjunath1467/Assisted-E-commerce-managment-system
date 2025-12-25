import { Bot, Lightbulb, ShieldCheck } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { RecommendedAction, ReportMessage } from "@/lib/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ─── Sub-sections ────────────────────────────────────────────────────────────

function RecommendationsSection({
  recommendations,
}: {
  recommendations: RecommendedAction[];
}) {
  return (
    <div className="flex flex-col gap-2">
      {recommendations.map((rec, i) => (
        <div
          key={i}
          className="rounded-lg border border-border bg-card p-3 shadow-sm"
        >
          <div className="mb-1.5 flex items-center gap-2">
            <Badge variant="outline" className="text-[0.65rem] font-semibold">
              {rec.action_type.replace(/_/g, " ")}
            </Badge>
            {rec.requires_approval && (
              <Badge variant="secondary" className="text-[0.65rem]">
                Needs approval
              </Badge>
            )}
          </div>
          <p className="text-sm font-medium text-foreground">
            {rec.description}
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            {rec.rationale}
          </p>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

interface Props {
  message: ReportMessage;
}

export function ReportCard({ message }: Props) {
  const { report } = message;
  const time = formatDate(message.timestamp);
  const hasAccordions = report.recommendations.length > 0;

  return (
    <div className="flex w-full max-w-3xl items-end gap-2">
      <div className="mb-5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Bot className="size-4" />
      </div>
      <div className="flex flex-1 flex-col items-start gap-1">
        <div className="w-full rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-3.5 shadow-sm">
          {/* Summary */}
          <p className="text-sm leading-relaxed text-foreground/90 font-[450]">
            {report.summary}
          </p>

          {hasAccordions && <Separator className="my-3" />}

          {hasAccordions && (
            <Accordion>
              <AccordionItem value="recommendations">
                <AccordionTrigger>
                  <Lightbulb className="mr-2 size-4 shrink-0 text-muted-foreground" />
                  Recommendations
                  <Badge
                    variant="secondary"
                    className="ml-auto mr-3 text-[0.65rem]"
                  >
                    {report.recommendations.length}
                  </Badge>
                </AccordionTrigger>
                <AccordionContent>
                  <RecommendationsSection
                    recommendations={report.recommendations}
                  />
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}

          {report.incident_id && (
            <div className="mt-3 flex items-center gap-1 text-[0.7rem] text-muted-foreground">
              <ShieldCheck className="size-3 text-muted-foreground" />
              <span className="font-mono">
                {report.incident_id.slice(0, 8)}
              </span>
            </div>
          )}
        </div>
        <span className="pl-1 text-[0.7rem] font-medium text-muted-foreground">
          {time}
        </span>
      </div>
    </div>
  );
}
