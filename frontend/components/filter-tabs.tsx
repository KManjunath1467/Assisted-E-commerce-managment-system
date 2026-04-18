"use client";

interface Tab<T extends string> {
  key: T;
  label: string;
  count: number;
}

interface Props<T extends string> {
  tabs: Tab<T>[];
  activeTab: T;
  /** Key of the tab whose count badge gets amber "warning" styling. */
  warningKey?: T;
  onChange: (key: T) => void;
}

export function FilterTabs<T extends string>({
  tabs,
  activeTab,
  warningKey,
  onChange,
}: Props<T>) {
  return (
    <div className="shrink-0 border-b border-border bg-background px-6">
      <div className="mx-auto flex max-w-3xl gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
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
                  ? tab.key === warningKey
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
  );
}
