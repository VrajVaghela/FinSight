"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Globe, Square } from "lucide-react";
import { useLanguageDetect } from "@/hooks/useLanguageDetect";

interface InputBarProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  // Voice input
  voiceState?: "idle" | "listening" | "processing" | "error";
  interimTranscript?: string;
  voiceError?: string | null;
  onToggleVoice?: () => void;
}

export default function InputBar({
  onSend,
  disabled,
  voiceState = "idle",
  interimTranscript = "",
  voiceError = null,
  onToggleVoice,
}: InputBarProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { detect } = useLanguageDetect();
  const detected = text ? detect(text) : "en";

  const isListening = voiceState === "listening";
  const isProcessing = voiceState === "processing";

  useEffect(() => { inputRef.current?.focus(); }, []);

  // When voice produces a transcript, inject into input box
  useEffect(() => {
    if (interimTranscript) {
      setText(interimTranscript);
    }
  }, [interimTranscript]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div style={{ padding: "16px 24px 20px", borderTop: "1px solid #1e1e1e", background: "#111111" }}>
      {/* Interim transcript preview */}
      {isListening && interimTranscript && (
        <div
          className="animate-fade-in"
          style={{
            marginBottom: 8,
            padding: "6px 14px",
            background: "rgba(239,68,68,0.07)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10,
            fontSize: 13,
            color: "#ef4444",
            fontStyle: "italic",
          }}
        >
          🎤 {interimTranscript}
        </div>
      )}

      {/* Error */}
      {voiceError && (
        <div
          className="animate-fade-in"
          style={{
            marginBottom: 8,
            padding: "6px 14px",
            background: "rgba(239,68,68,0.07)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10,
            fontSize: 12,
            color: "#ef4444",
          }}
        >
          ⚠️ {voiceError}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ position: "relative" }}>
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            isListening ? "Listening…" :
            isProcessing ? "Processing speech…" :
            "Ask about your documents…"
          }
          disabled={disabled || isListening}
          style={{
            width: "100%",
            background: isListening ? "rgba(239,68,68,0.04)" : "#0a0a0a",
            border: "1px solid",
            borderColor: isListening ? "rgba(239,68,68,0.4)" : "#2a2a2a",
            borderRadius: 16,
            padding: "16px 150px 16px 20px",
            fontSize: 14,
            fontWeight: 500,
            color: "#fafafa",
            outline: "none",
            transition: "all 0.2s ease",
            fontFamily: "inherit",
          }}
          onFocus={(e) => { if (!isListening) e.currentTarget.style.borderColor = "#333"; }}
          onBlur={(e) => { if (!isListening) e.currentTarget.style.borderColor = "#2a2a2a"; }}
        />

        <div style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)", display: "flex", alignItems: "center", gap: 4 }}>
          {/* Language indicator */}
          {detected && detected !== "en" && (
            <div
              className="animate-scale-in"
              style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 8, background: "rgba(167,139,250,0.08)", border: "1px solid rgba(167,139,250,0.15)" }}
            >
              <Globe style={{ width: 11, height: 11, color: "#a78bfa" }} />
              <span style={{ fontSize: 10, fontWeight: 700, color: "#a78bfa", textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>
                {detected}
              </span>
            </div>
          )}

          {/* Voice input button */}
          {onToggleVoice && (
            <button
              type="button"
              onClick={onToggleVoice}
              title={isListening ? "Stop recording" : "Voice input"}
              style={{
                width: 36,
                height: 36,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 10,
                border: "none",
                background: isListening ? "rgba(239,68,68,0.15)" : "transparent",
                color: isListening ? "#ef4444" : "#555",
                cursor: "pointer",
                transition: "all 0.15s ease",
                position: "relative",
              }}
            >
              {isListening ? (
                <>
                  <MicOff style={{ width: 16, height: 16 }} />
                  {/* Pulse ring */}
                  <span style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: 10,
                    border: "2px solid #ef4444",
                    animation: "pulse-ring 1.2s ease-out infinite",
                    opacity: 0.6,
                  }} />
                </>
              ) : isProcessing ? (
                <div style={{ width: 16, height: 16, border: "2px solid #a78bfa", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
              ) : (
                <Mic style={{ width: 16, height: 16 }} />
              )}
            </button>
          )}

          {/* Send button */}
          <button
            type="submit"
            disabled={!text.trim() || disabled || isListening}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 36,
              height: 36,
              borderRadius: 10,
              border: "none",
              background: text.trim() && !isListening ? "#22c55e" : "#222",
              color: text.trim() && !isListening ? "black" : "#555",
              cursor: text.trim() && !isListening ? "pointer" : "default",
              transition: "all 0.2s ease",
            }}
          >
            <Send style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </form>

      {/* Status Bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 10, padding: "0 4px" }}>
        {[
          { label: isListening ? "Recording" : "Connected", color: isListening ? "#ef4444" : "#22c55e" },
          { label: "RAG Ready", color: "#a78bfa" },
          { label: "Docs Synced", color: "#3b82f6" },
        ].map((item) => (
          <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: item.color }} />
            <span style={{ fontSize: 10, fontWeight: 600, color: "#444", fontFamily: "'JetBrains Mono', monospace" }}>
              {item.label}
            </span>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.5); opacity: 0; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
