"use client";

import { useState, useCallback, useRef } from "react";
import type {
  Citation,
  RetrievedChunk,
  UIComponent,
  PALResult,
  ChatRequest,
} from "@/types";
import { openChatStream } from "@/lib/api";
import { metricsStore } from "@/lib/metrics";

export function useSSEStream() {
  const [streamingText, setStreamingText] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [debugChunks, setDebugChunks] = useState<RetrievedChunk[]>([]);
  const [queryRewritten, setQueryRewritten] = useState("");
  const [uiComponent, setUiComponent] = useState<UIComponent | null>(null);
  const [palResult, setPalResult] = useState<PALResult | null>(null);
  const [refusal, setRefusal] = useState<{ reason: string; message: string } | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const citationSetRef = useRef<Set<string>>(new Set());

  const resetState = useCallback(() => {
    setStreamingText("");
    setCitations([]);
    setDebugChunks([]);
    setQueryRewritten("");
    setUiComponent(null);
    setPalResult(null);
    setRefusal(null);
    setRunId(null);
    setError(null);
    setConversationId(null);
    citationSetRef.current = new Set();
  }, []);

  const sendMessage = useCallback(
    async (request: ChatRequest) => {
      // Abort previous stream if any
      if (controllerRef.current) {
        controllerRef.current.abort();
      }

      resetState();
      setIsStreaming(true);

      const startTime = Date.now();
      let wasRefusal = false;

      const controller = await openChatStream(
        request,
        // onEvent handler
        (event: Record<string, unknown>) => {
          const type = event.type as string;

          switch (type) {
            case "chunk": {
              const delta = event.delta as string;
              setStreamingText((prev) => prev + delta);

              // Process citations
              const newCitations = event.citations as { chunk_id: string; page: number; score: number }[] | undefined;
              if (newCitations && newCitations.length > 0) {
                setCitations((prev) => {
                  const updated = [...prev];
                  for (const c of newCitations) {
                    if (!citationSetRef.current.has(c.chunk_id)) {
                      citationSetRef.current.add(c.chunk_id);
                      updated.push({
                        chunk_id: c.chunk_id,
                        page: c.page,
                        score: c.score,
                        section_header: null,
                        text_snippet: "",
                        bounding_box: null,
                      });
                    }
                  }
                  return updated;
                });
              }
              break;
            }

            case "retrieval_debug": {
              setDebugChunks(event.chunks as RetrievedChunk[]);
              setQueryRewritten(event.query_rewritten as string);
              setRunId(event.run_id as string);
              break;
            }

            case "ui_component": {
              setUiComponent({
                component: event.component as UIComponent["component"],
                data: event.data as UIComponent["data"],
              });
              break;
            }

            case "pal_execution": {
              setPalResult({
                code: event.code as string,
                result: event.result as string,
                label: event.label as string,
              });
              break;
            }

            case "refusal": {
              wasRefusal = true;
              setRefusal({
                reason: event.reason as string,
                message: event.message as string,
              });
              break;
            }

            case "done": {
              const newConvId = event.conversation_id as string;
              setConversationId(newConvId);
              setRunId(event.run_id as string);

              // Record metrics
              metricsStore.record({
                latency_ms: (event.latency_ms as number) || Date.now() - startTime,
                total_tokens: (event.total_tokens as number) || 0,
                cached_tokens: (event.cached_tokens as number) || 0,
                timestamp: Date.now(),
                wasRefusal,
              });
              break;
            }
          }
        },
        // onError
        (err) => {
          setError(err.message);
        },
        // onDone
        () => {
          setIsStreaming(false);
        }
      );

      controllerRef.current = controller;
    },
    [resetState]
  );

  const abort = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      setIsStreaming(false);
    }
  }, []);

  return {
    streamingText,
    citations,
    debugChunks,
    queryRewritten,
    uiComponent,
    palResult,
    refusal,
    runId,
    conversationId,
    isStreaming,
    error,
    sendMessage,
    abort,
    reset: resetState,
  };
}
