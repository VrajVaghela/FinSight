"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchFileStatus } from "@/lib/api";

export type IngestionStatus = "idle" | "pending" | "processing" | "ready" | "failed";

export function useIngestionStatus() {
  const [status, setStatus] = useState<IngestionStatus>("idle");
  const [pageCount, setPageCount] = useState<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPolling = useCallback((targetFileId: string) => {
    if (!targetFileId) return;
    setStatus("pending");

    intervalRef.current = setInterval(async () => {
      try {
        const data = await fetchFileStatus(targetFileId);
        setStatus(data.status as IngestionStatus);

        if (data.status === "ready") {
          // If the backend doesn't return page_count in this specific endpoint, 
          // we might need another way to get it, but 'ready' is enough for the UI.
          if (intervalRef.current) clearInterval(intervalRef.current);
        } else if (data.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 2000);
  }, []);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return { status, pageCount, startPolling, stopPolling };
}
