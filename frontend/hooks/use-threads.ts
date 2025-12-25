"use client";

import { useCallback, useEffect, useState } from "react";
import { getThreads } from "@/lib/api";
import type { ThreadSummary } from "@/lib/types";

export function useThreads() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchThreads = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getThreads();
      setThreads(data);
    } catch {
      // Silently ignore — sidebar just stays empty if the fetch fails
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  return { threads, isLoading, fetchThreads };
}
