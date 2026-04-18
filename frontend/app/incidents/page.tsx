"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { getIncidents, resolveIncident } from "@/lib/api";
import type { Incident } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FilterTabs } from "@/components/filter-tabs";
import { PageHeader } from "@/components/page-header";

function IncidentCard({
  incident,
  onUpdate,
}: {
  incident: Incident;
  onUpdate: (updated: Incident) => void;
}) {
  const [expanded, setExpanded] = useState(incident.status === "open");
  const [resolving, setResolving] = useState(false);
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [resolutionSummary, setResolutionSummary] = useState("");

  const isOpen = incident.status === "open";

  const [resolveError, setResolveError] = useState<string | null>(null);

  async function handleResolve() {
    setResolving(true);
    setResolveError(null);
    try {
      const updated = await resolveIncident(
        incident.id,
        resolutionSummary.trim() || null,
      );
      onUpdate(updated);
      setShowResolveForm(false);
      setResolutionSummary("");
    } catch (err) {
      setResolveError(
        err instanceof Error ? err.message : "Failed to resolve incident.",
      );
    } finally {
      setResolving(false);
    }
  }

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div className="flex flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={isOpen ? "secondary" : "outline"}
                className={
                  isOpen
                    ? "bg-warning/10 text-warning border-0"
                    : "text-muted-foreground"
                }
              >
                {isOpen ? "Open" : "Resolved"}
              </Badge>
              <span className="text-[0.7rem] text-muted-foreground ml-auto">
                {new Date(incident.created_at).toLocaleString([], {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </span>
            </div>
            <p className="text-sm font-medium text-foreground leading-snug">
              {incident.summary ?? "No summary available"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="shrink-0 rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {expanded ? (
              <ChevronUp className="size-4" />
            ) : (
              <ChevronDown className="size-4" />
            )}
          </button>
        </div>
      </CardHeader>

      {expanded && (
        <>
          {(incident.resolved_at || incident.resolution_summary) && (
            <>
              <Separator />
              <CardContent className="flex flex-col gap-2 pt-4">
                {incident.resolved_at && (
                  <p className="text-[0.7rem] text-muted-foreground">
                    Resolved{" "}
                    {new Date(incident.resolved_at).toLocaleString([], {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </p>
                )}
                {incident.resolution_summary && (
                  <div className="rounded-md bg-muted/50 px-3 py-2">
                    <p className="text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Resolution note
                    </p>
                    <p className="text-sm text-foreground">
                      {incident.resolution_summary}
                    </p>
                  </div>
                )}
              </CardContent>
            </>
          )}

          {isOpen && (
            <>
              {(incident.resolved_at || incident.resolution_summary) && (
                <Separator />
              )}
              <CardFooter className="flex flex-col gap-3 pt-3">
                {resolveError && (
                  <div className="w-full rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                    {resolveError}
                  </div>
                )}
                {showResolveForm ? (
                  <>
                    <Textarea
                      placeholder="Optional: describe how this incident was resolved…"
                      value={resolutionSummary}
                      onChange={(e) => setResolutionSummary(e.target.value)}
                      rows={3}
                      className="text-sm resize-none"
                    />
                    <div className="flex gap-2 self-end">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={resolving}
                        onClick={() => {
                          setShowResolveForm(false);
                          setResolutionSummary("");
                        }}
                        className="text-xs"
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={resolving}
                        onClick={handleResolve}
                        className="text-xs text-success border-success/30 hover:bg-success/10 hover:border-success/40"
                      >
                        {resolving ? (
                          <Loader2 className="mr-1.5 size-3 animate-spin" />
                        ) : (
                          <CheckCircle className="mr-1.5 size-3" />
                        )}
                        Confirm Resolution
                      </Button>
                    </div>
                  </>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setShowResolveForm(true)}
                    className="ml-auto text-xs"
                  >
                    <CheckCircle className="mr-1.5 size-3" />
                    Mark as Resolved
                  </Button>
                )}
              </CardFooter>
            </>
          )}
        </>
      )}
    </Card>
  );
}

type IncidentFilter = "open" | "resolved" | "all";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<IncidentFilter>("open");

  const fetchIncidents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getIncidents();
      setIncidents(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load incidents.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  function handleUpdate(updated: Incident) {
    setIncidents((prev) =>
      prev.map((i) => (i.id === updated.id ? updated : i)),
    );
  }

  const openCount = incidents.filter((i) => i.status === "open").length;
  const resolvedCount = incidents.filter((i) => i.status === "resolved").length;

  const filteredIncidents =
    activeTab === "all"
      ? incidents
      : incidents.filter((i) => i.status === activeTab);

  const tabs: { key: IncidentFilter; label: string; count: number }[] = [
    { key: "open", label: "Open", count: openCount },
    { key: "resolved", label: "Resolved", count: resolvedCount },
    { key: "all", label: "All", count: incidents.length },
  ];

  return (
    <div className="flex h-screen flex-col bg-background">
      <PageHeader
        page="incidents"
        icon={AlertCircle}
        title="Incidents"
        badgeText={openCount > 0 ? `${openCount} open` : undefined}
        isLoading={isLoading}
        onRefresh={fetchIncidents}
      />
      <FilterTabs
        tabs={tabs}
        activeTab={activeTab}
        warningKey="open"
        onChange={setActiveTab}
      />

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {isLoading && incidents.length === 0 && (
            <>
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {!isLoading && !error && filteredIncidents.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <CheckCircle className="size-10 text-success" />
              <p className="text-sm font-medium text-foreground">
                {activeTab === "open"
                  ? "No open incidents"
                  : "No incidents found"}
              </p>
              <p className="text-xs text-muted-foreground">
                {activeTab === "open"
                  ? "All clear — nothing requires attention right now."
                  : "Try a different filter."}
              </p>
            </div>
          )}

          {filteredIncidents.map((incident) => (
            <IncidentCard
              key={incident.id}
              incident={incident}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
