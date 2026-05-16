"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSSEStream } from "@/hooks/useSSEStream";
import { useVoice } from "@/hooks/useVoice";
import MessageBubble from "./chat/MessageBubble";
import TypingIndicator from "./chat/TypingIndicator";
import InputBar from "./chat/InputBar";
import VoiceSpeaker from "./chat/VoiceSpeaker";
import GenUIRouter from "./widgets/GenUIRouter";
import { Target, RefreshCw } from "lucide-react";
import type { ChatMessage, UIComponent } from "@/types";
import RAGEvaluator from "./chat/RAGEvaluator";

interface ChatContainerProps {
  projectId: string;
  conversationId?: string;
  onDebugUpdate?: (data: Record<string, unknown>) => void;
  onCitationClick?: (chunkId: string) => void;
}

export default function ChatContainer({
  projectId,
  conversationId,
  onDebugUpdate,
  onCitationClick,
}: ChatContainerProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [genUIPayloads, setGenUIPayloads] = useState<Record<string, unknown>[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [sessionScope, setSessionScope] = useState<string | null>(null);
  // ID of the message currently being spoken (for TTS highlight)
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState<number | null>(null);

  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    conversationId || null
  );

  const {
    streamingText,
    isStreaming,
    sendMessage,
    uiComponent: sseUiComponent,
    citations: sseCitations,
    debugChunks,
    queryRewritten,
    refusal,
    runId,
    conversationId: sseConversationId,
  } = useSSEStream();

  // ── Voice ──────────────────────────────────────────────────────────────
  // Use a ref so the voice callback always has the latest handleSend
  const handleSendRef = useRef<((text: string) => void) | null>(null);
  const lastInputWasVoiceRef = useRef(false);
  const handleVoiceTranscript = useCallback((text: string) => {
    lastInputWasVoiceRef.current = true;
    handleSendRef.current?.(text);
  }, []);

  const voice = useVoice({ onTranscript: handleVoiceTranscript });

  const handleToggleVoice = () => {
    if (voice.inputState === "listening") {
      voice.stopListening();
    } else {
      voice.startListening();
    }
  };

  const handleSpeak = (text: string, idx: number) => {
    setSpeakingMsgIdx(idx);
    voice.speak(text);
  };

  const handleStopSpeak = () => {
    setSpeakingMsgIdx(null);
    voice.stopSpeaking();
  };

  // Clear speaking index when TTS finishes naturally
  useEffect(() => {
    if (voice.outputState === "idle") setSpeakingMsgIdx(null);
  }, [voice.outputState]);

  // Load history if conversationId is provided
  useEffect(() => {
    if (conversationId) {
      setActiveConversationId(conversationId);
      import("@/lib/api").then(({ fetchConversationHistory }) => {
        fetchConversationHistory(conversationId)
          .then((history) => {
            const formatted = history.map((msg: any) => ({
              role: msg.role as "user" | "assistant",
              content: msg.content,
              timestamp: new Date(msg.created_at).toLocaleTimeString(),
              citations: (msg.citations || []).map((c: any) => ({
                chunkId: c.chunk_id,
                page: c.page,
                score: c.score,
              })),
              uiComponents: msg.ui_components || [],
            }));
            setMessages(formatted);
          })
          .catch(console.error);
      });
    } else {
      setActiveConversationId(null);
      setMessages([]);
      setGenUIPayloads([]);
    }
  }, [conversationId]);

  // When SSE returns a new conversation ID, update the URL so the chat persists
  useEffect(() => {
    if (sseConversationId && sseConversationId !== activeConversationId) {
      setActiveConversationId(sseConversationId);
      // Update URL so Next.js router knows we are no longer on the "New Chat" route
      if (projectId && projectId !== "standalone") {
        const newUrl = `/projects/${projectId}/chat/${sseConversationId}`;
        router.replace(newUrl);
      }
    }
  }, [sseConversationId, activeConversationId, projectId]);

  // Forward debug data up when it changes
  useEffect(() => {
    if (debugChunks.length > 0 && onDebugUpdate) {
      onDebugUpdate({ event: "debug", chunks: debugChunks, query_rewritten: queryRewritten });
    }
  }, [debugChunks, queryRewritten, onDebugUpdate]);

  // Handle UI component events
  useEffect(() => {
    if (sseUiComponent) {
      setGenUIPayloads((prev) => [...prev, { event: "ui_component", ...sseUiComponent } as Record<string, unknown>]);
    }
  }, [sseUiComponent]);

  // When streaming completes, add assistant message + auto-speak if voice input was used
  const prevStreamingRef = useRef(false);
  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming && streamingText) {
      const newIdx = messages.length; // index of the new message
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant" as const,
          content: streamingText,
          timestamp: new Date().toLocaleTimeString(),
          citations: sseCitations.map(c => ({
            chunkId: c.chunk_id,
            page: c.page,
            score: c.score,
          })),
          uiComponents: genUIPayloads.map(p => ({
            component: p.component as any,
            data: p.data as any
          })),
        },
      ]);
      setGenUIPayloads([]); // Clear temporary payloads once added to message
      // Auto-speak if the last query came from voice input
      if (lastInputWasVoiceRef.current) {
        lastInputWasVoiceRef.current = false;
        setTimeout(() => {
          setSpeakingMsgIdx(newIdx);
          voice.speak(streamingText);
        }, 300);
      }
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, streamingText, sseCitations]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, streamingText, isOptimizing]);

  const handleSend = (text: string) => {
    handleSendRef.current = handleSend; // keep ref in sync
    // 1. Add user message
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: text,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
    setGenUIPayloads([]);
    
    // 2. Query Optimizer Flow
    setIsOptimizing(true);
    
    setTimeout(() => {
      setIsOptimizing(false);
      
      const lowerText = text.toLowerCase();
      
      // Mock: Code Diff Suggestion
      if (lowerText.includes("diff") || lowerText.includes("code")) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "I've rewritten your query to explicitly request edge-case handling. Here is the suggested change to `calculateMargins`:",
            timestamp: new Date().toLocaleTimeString(),
            diffSuggestion: {
              filename: "utils/finance.ts",
              language: "typescript",
              hunks: [
                {
                  oldStart: 45,
                  newStart: 45,
                  lines: [
                    { type: "context", content: "  export function calculateMargins(revenue: number, costs: number) {" },
                    { type: "remove", content: "    return (revenue - costs) / revenue;" },
                    { type: "add", content: "    if (revenue === 0) return 0;" },
                    { type: "add", content: "    const margin = (revenue - costs) / revenue;" },
                    { type: "add", content: "    return Number(margin.toFixed(4));" },
                    { type: "context", content: "  }" }
                  ]
                }
              ]
            }
          }
        ]);
        return;
      }

      // Mock: Generative UI ComparisonChart
      if (lowerText.includes("compare") || lowerText.includes("comparison")) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Based on the documents, here is the revenue and profit comparison across the last four quarters:",
            timestamp: new Date().toLocaleTimeString(),
            uiComponent: {
              component: "ComparisonChart",
              data: {
                title: "Financial Performance Comparison",
                description: "Quarterly Revenue vs. Gross Profit (in millions)",
                metrics: [
                  { key: "revenue", name: "Revenue", color: "#22c55e" },
                  { key: "profit", name: "Gross Profit", color: "#a78bfa" }
                ],
                data: [
                  { category: "Q1", revenue: 4500, profit: 1200 },
                  { category: "Q2", revenue: 4800, profit: 1350 },
                  { category: "Q3", revenue: 5100, profit: 1500 },
                  { category: "Q4", revenue: 6200, profit: 2100 }
                ]
              }
            } as UIComponent
          }
        ]);
        return;
      }

      // Default fallback stream — pass the active conversation ID
        sendMessage({
          project_id: projectId,
          message: text,
          conversation_id: activeConversationId || conversationId || null,
          language: "en",
          voice: false,
          debug_mode: true,
        });
    }, 1500); // 1.5s simulated optimization delay
  };

  const isEmpty = messages.length === 0 && !isStreaming && !isOptimizing;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
      
      {/* Session Scope Indicator */}
      {sessionScope && (
        <div style={{ 
          position: "absolute", 
          top: 16, 
          left: "50%", 
          transform: "translateX(-50%)", 
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "6px 16px",
          background: "rgba(20,20,20,0.85)",
          backdropFilter: "blur(12px)",
          border: "1px solid #2a2a2a",
          borderRadius: 99,
          boxShadow: "0 4px 12px rgba(0,0,0,0.2)"
        }} className="animate-fade-down">
          <Target size={14} color="#a78bfa" />
          <span style={{ fontSize: 12, color: "#aaa", fontWeight: 500 }}>
            Search limited to <span style={{ color: "#fafafa" }}>{sessionScope}</span>
          </span>
          <button 
            onClick={() => setSessionScope(null)}
            style={{ 
              background: "transparent", 
              border: "none", 
              color: "#22c55e", 
              fontSize: 11, 
              fontWeight: 600, 
              cursor: "pointer",
              marginLeft: 8 
            }}
          >
            Search Entire Document
          </button>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "64px 24px 32px", // Extra top padding for the absolute scope badge
        }}
      >
        {isEmpty ? (
          <div
            className="animate-fade-up stagger-children"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              gap: 24,
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 16,
                background: "rgba(34,197,94,0.08)",
                border: "1px solid rgba(34,197,94,0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              className="animate-glow"
            >
              <span style={{ fontSize: 24 }}>✦</span>
            </div>

            <div style={{ textAlign: "center" }}>
              <h2
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#fafafa",
                  marginBottom: 8,
                  letterSpacing: "-0.02em",
                }}
              >
                Ready to Analyze
              </h2>
              <p
                style={{
                  fontSize: 14,
                  color: "#666",
                  lineHeight: 1.6,
                  maxWidth: 400,
                }}
              >
                Ask questions about your documents. Every answer is grounded
                with citations traceable to the source.
              </p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
                marginTop: 8,
                width: "100%",
                maxWidth: 600,
              }}
            >
              {[
                {
                  label: "Comparison",
                  text: "Compare revenue across quarters",
                  color: "#a78bfa",
                },
                {
                  label: "Past Data Flow",
                  text: "What was the revenue then vs now?",
                  color: "#22c55e",
                },
                {
                  label: "Diff Suggestion",
                  text: "Can you provide a diff for the finance util?",
                  color: "#3b82f6",
                },
              ].map((example) => (
                <button
                  key={example.label}
                  className="hover-lift animate-fade-up"
                  onClick={() => handleSend(example.text)}
                  style={{
                    textAlign: "left",
                    padding: "16px",
                    background: "#151515",
                    border: "1px solid #2a2a2a",
                    borderRadius: 12,
                    cursor: "pointer",
                    transition: "all 0.25s cubic-bezier(0.16,1,0.3,1)",
                  }}
                >
                  <p
                    style={{
                      fontSize: 9,
                      fontWeight: 800,
                      color: example.color,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      marginBottom: 8,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {example.label}
                  </p>
                  <p
                    style={{
                      fontSize: 13,
                      color: "#999",
                      lineHeight: 1.5,
                      fontWeight: 500,
                    }}
                  >
                    {example.text}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {messages.map((msg, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  timestamp={msg.timestamp}
                  citations={msg.citations}
                  diffSuggestion={msg.diffSuggestion}
                  onCitationClick={onCitationClick}
                />

                {/* TTS speaker for assistant messages */}
                {msg.role === "assistant" && (
                  <div style={{ paddingLeft: 44 }}>
                    <VoiceSpeaker
                      text={msg.content}
                      outputState={speakingMsgIdx === i ? voice.outputState : "idle"}
                      onSpeak={(text) => handleSpeak(text, i)}
                      onStop={handleStopSpeak}
                    />
                  </div>
                )}

                {/* Render Inline UI Components if attached to message */}
                {msg.uiComponent && (
                  <div className="animate-fade-up" style={{ width: "100%", maxWidth: 720, marginRight: "auto", paddingLeft: 44 }}>
                    <GenUIRouter uiComponent={msg.uiComponent} />
                  </div>
                )}
                {msg.uiComponents && msg.uiComponents.map((comp, idx) => (
                  <div key={idx} className="animate-fade-up" style={{ width: "100%", maxWidth: 720, marginRight: "auto", paddingLeft: 44 }}>
                    <GenUIRouter uiComponent={comp} />
                  </div>
                ))}
                
                {/* RAG Evaluator for the latest assistant message */}
                {msg.role === "assistant" && i === messages.length - 1 && !isStreaming && debugChunks.length > 0 && (
                  <div className="animate-fade-in" style={{ paddingLeft: 44, paddingBottom: 16 }}>
                    <RAGEvaluator 
                      query={messages[i - 1]?.content || ""}
                      answer={msg.content}
                      contexts={debugChunks.map(c => c.text_snippet)}
                    />
                  </div>
                )}
              </div>
            ))}

            {isOptimizing && (
              <div className="animate-fade-in" style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 44 }}>
                <RefreshCw size={14} className="animate-spin" color="#a78bfa" />
                <span style={{ fontSize: 13, color: "#a78bfa", fontWeight: 500 }}>Optimizing query for retrieval...</span>
              </div>
            )}

            {isStreaming && streamingText && (
               <MessageBubble
                 role="assistant"
                 content={streamingText}
                 isStreaming
                 onCitationClick={onCitationClick}
               />
             )}

            {isStreaming && !streamingText && !isOptimizing && <TypingIndicator />}

            {/* GenUI Payload from SSE */}
            {genUIPayloads.map((payload, i) => (
              <div
                key={`genui-${i}`}
                className="animate-fade-up"
                style={{ width: "100%", maxWidth: 720, marginRight: "auto", paddingLeft: 44 }}
              >
                {/* Requires passing uiComponent properly, assuming event matches type */}
                <GenUIRouter uiComponent={payload as unknown as UIComponent} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <InputBar
        onSend={handleSend}
        disabled={isStreaming || isOptimizing}
        voiceState={voice.inputState}
        interimTranscript={voice.interimTranscript}
        voiceError={voice.inputError}
        onToggleVoice={voice.isSupported ? handleToggleVoice : undefined}
      />
    </div>
  );
}
