"use client";

import { useEffect, useRef, useState } from "react";

interface Tab<T extends string> {
  key: T;
  label: string;
  count: number;
}

interface Props<T extends string> {
  tabs: Tab<T>[];
  activeTab: T;
  /** Key of the tab whose count badge gets warning styling. */
  warningKey?: T;
  onChange: (key: T) => void;
}

export function FilterTabs<T extends string>({
  tabs,
  activeTab,
  warningKey,
  onChange,
}: Props<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [indicator, setIndicator] = useState({ left: 0, width: 0, ready: false });

  const activeIdx = tabs.findIndex((t) => t.key === activeTab);

  useEffect(() => {
    const el = tabRefs.current[activeIdx];
    const container = containerRef.current;
    if (!el || !container) return;
    const containerRect = container.getBoundingClientRect();
    const tabRect = el.getBoundingClientRect();
    setIndicator({
      left: tabRect.left - containerRect.left,
      width: tabRect.width,
      ready: true,
    });
  }, [activeIdx, activeTab]);

  return (
    <div className="shrink-0 border-b border-border bg-background px-6">
      <div ref={containerRef} className="relative mx-auto flex max-w-3xl gap-1">
        {tabs.map((tab, i) => (
          <button
            key={tab.key}
            ref={(el) => {
              tabRefs.current[i] = el;
            }}
            type="button"
            onClick={() => onChange(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors focus-visible:outline-none ${
              activeTab === tab.key
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
            <span
              className={`rounded-full px-1.5 py-0.5 text-[0.6rem] font-semibold ${
                tab.key === warningKey
                  ? "bg-warning/15 text-warning"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
        {indicator.ready && (
          <span
            className="absolute bottom-0 h-0.5 bg-primary transition-all duration-200"
            style={{ left: indicator.left, width: indicator.width }}
          />
        )}
      </div>
    </div>
  );
}
