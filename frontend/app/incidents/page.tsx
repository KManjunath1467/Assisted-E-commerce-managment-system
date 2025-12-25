"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  MessageSquare,
  RefreshCw,
  Zap,
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
import { Textarea } from "@/components/ui/textarea";
import { ThemeToggle } from "@/components/theme-toggle";

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

  async function handleResolve() {
    setResolving(true);
    try {
      const updated = await resolveIncident(
        incident.id,
        resolutionSummary.trim() || null,
      );
      onUpdate(updated);
      setShowResolveForm(false);
      setResolutionSummary("");
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
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-0"
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
                        className="text-xs text-emerald-700 border-emerald-300 hover:bg-emerald-50 hover:border-emerald-400 dark:text-emerald-400 dark:border-emerald-800 dark:hover:bg-emerald-950"
                      >
                        {resolving ? (
                          <Clock className="mr-1.5 size-3 animate-spin" />
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
      {/* Header */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-background/90 px-6 py-3 backdrop-blur-sm shadow-sm">
        <AlertCircle className="size-5 text-primary" />
        <span className="text-sm font-semibold text-foreground">Incidents</span>
        {openCount > 0 && (
          <Badge variant="secondary" className="text-[0.65rem]">
            {openCount} open
          </Badge>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Link href="/">
            <Button variant="ghost" size="sm" className="text-xs gap-1.5">
              <MessageSquare className="size-3.5" />
              Chat
            </Button>
          </Link>
          <Link href="/actions">
            <Button variant="ghost" size="sm" className="text-xs gap-1.5">
              <Zap className="size-3.5" />
              Actions
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchIncidents}
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
                    ? tab.key === "open"
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
          {isLoading && incidents.length === 0 && (
            <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
              <RefreshCw className="mr-2 size-4 animate-spin" />
              Loading incidents…
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {!isLoading && !error && filteredIncidents.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <CheckCircle className="size-10 text-emerald-500" />
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
