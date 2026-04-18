"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, MessageSquare, RefreshCw, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_LINKS: Record<string, NavLink[]> = {
  actions: [
    { href: "/", label: "Chat", icon: MessageSquare },
    { href: "/incidents", label: "Incidents", icon: AlertCircle },
  ],
  incidents: [
    { href: "/", label: "Chat", icon: MessageSquare },
    { href: "/actions", label: "Actions", icon: Zap },
  ],
};

interface Props {
  /** Which page this header is on — determines nav links shown. */
  page: "actions" | "incidents";
  icon: LucideIcon;
  title: string;
  /** Badge text shown next to the title (e.g. "3 pending"). Omit to hide. */
  badgeText?: string;
  isLoading: boolean;
  onRefresh: () => void;
}

export function PageHeader({
  page,
  icon: Icon,
  title,
  badgeText,
  isLoading,
  onRefresh,
}: Props) {
  const pathname = usePathname();

  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-border bg-background/90 px-6 py-3 backdrop-blur-sm shadow-sm">
      <Icon className="size-5 text-primary" />
      <span className="text-sm font-semibold text-foreground">{title}</span>
      {badgeText && (
        <Badge variant="secondary" className="text-[0.65rem]">
          {badgeText}
        </Badge>
      )}
      <div className="ml-auto flex items-center gap-2">
        {NAV_LINKS[page].map(({ href, label, icon: NavIcon }) => {
          const isActive = pathname === href;
          return (
            <Link key={href} href={href}>
              <Button
                variant="ghost"
                size="sm"
                className={`text-xs gap-1.5 ${
                  isActive
                    ? "text-foreground font-semibold bg-muted/60"
                    : ""
                }`}
              >
                <NavIcon className="size-3.5" />
                {label}
              </Button>
            </Link>
          );
        })}
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
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
  );
}
