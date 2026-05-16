"use client";

import { useState } from "react";
import Header from "@/components/Header";
import { Globe, Volume2, Info } from "lucide-react";

const languages = [
  "English", "Hindi", "Gujarati", "Tamil", "Bengali",
  "Arabic", "Spanish", "French", "German", "Chinese", "Japanese",
];

export default function SettingsPage() {
  const [selectedLang, setSelectedLang] = useState("English");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [ttsEnabled, setTtsEnabled] = useState(false);

  return (
    <>
      <Header />
      <div style={{ flex: 1, overflow: "auto", padding: 32 }}>
        <div className="animate-fade-up" style={{ maxWidth: 600, margin: "0 auto" }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#fafafa", marginBottom: 8, letterSpacing: "-0.03em" }}>
            Settings
          </h1>
          <p style={{ fontSize: 14, color: "#555", marginBottom: 32 }}>
            Configure language, voice, and platform preferences
          </p>

          {/* Language */}
          <div
            style={{
              padding: 24,
              background: "#151515",
              border: "1px solid #2a2a2a",
              borderRadius: 14,
              marginBottom: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <Globe style={{ width: 16, height: 16, color: "#a78bfa" }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: "#fafafa" }}>Language</span>
            </div>
            <p style={{ fontSize: 12, color: "#666", marginBottom: 16, lineHeight: 1.5 }}>
              Auto-detects from input text. You can also select manually.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {languages.map((lang) => (
                <button
                  key={lang}
                  onClick={() => setSelectedLang(lang)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 8,
                    border: "1px solid",
                    borderColor: selectedLang === lang ? "rgba(34,197,94,0.3)" : "#2a2a2a",
                    background: selectedLang === lang ? "rgba(34,197,94,0.06)" : "#191919",
                    color: selectedLang === lang ? "#22c55e" : "#888",
                    fontSize: 12,
                    fontWeight: selectedLang === lang ? 700 : 500,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {lang}
                </button>
              ))}
            </div>
          </div>

          {/* Voice */}
          <div
            style={{
              padding: 24,
              background: "#151515",
              border: "1px solid #2a2a2a",
              borderRadius: 14,
              marginBottom: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <Volume2 style={{ width: 16, height: 16, color: "#3b82f6" }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: "#fafafa" }}>Voice</span>
            </div>

            {[
              { label: "Voice input", enabled: voiceEnabled, toggle: () => setVoiceEnabled(!voiceEnabled) },
              { label: "Text-to-speech responses", enabled: ttsEnabled, toggle: () => setTtsEnabled(!ttsEnabled) },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 0",
                  borderBottom: "1px solid #1e1e1e",
                }}
              >
                <span style={{ fontSize: 13, color: "#aaa" }}>{item.label}</span>
                <button
                  onClick={item.toggle}
                  style={{
                    width: 40,
                    height: 22,
                    borderRadius: 99,
                    border: "none",
                    background: item.enabled ? "#22c55e" : "#333",
                    position: "relative",
                    cursor: "pointer",
                    transition: "background 0.2s ease",
                  }}
                >
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      background: "white",
                      position: "absolute",
                      top: 3,
                      left: item.enabled ? 21 : 3,
                      transition: "left 0.2s cubic-bezier(0.16,1,0.3,1)",
                    }}
                  />
                </button>
              </div>
            ))}
          </div>

          {/* About */}
          <div
            style={{
              padding: 24,
              background: "#151515",
              border: "1px solid #2a2a2a",
              borderRadius: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <Info style={{ width: 16, height: 16, color: "#f59e0b" }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: "#fafafa" }}>About</span>
            </div>
            <p style={{ fontSize: 13, color: "#888", lineHeight: 1.6, marginBottom: 16 }}>
              FinSight AI is an enterprise-grade financial document intelligence platform.
              It uses grounded RAG with hybrid retrieval (BM25 + Dense + RRF + Reranker),
              4-level refusal gating, PAL for numeric precision, and RAGAS-evaluated quality assurance.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              {["v2.5", "RAG Engine", "Claude 3.5"].map((tag) => (
                <span
                  key={tag}
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: "#191919",
                    border: "1px solid #2a2a2a",
                    color: "#666",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
