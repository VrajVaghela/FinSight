"use client";

import { useState, useRef, useEffect } from "react";
import { X, Sparkles } from "lucide-react";

interface NewProjectModalProps {
  onClose: () => void;
  onCreate: (name: string, systemPrompt?: string) => Promise<boolean>;
}

export default function NewProjectModal({ onClose, onCreate }: NewProjectModalProps) {
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    const created = await onCreate(name.trim(), systemPrompt.trim() || undefined);
    if (!created) {
      setError("Project could not be created. Check the backend terminal for details.");
    }
    setLoading(false);
  };

  return (
    <div
      className="animate-fade-in"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(8px)",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="animate-scale-in"
        style={{
          width: "100%",
          maxWidth: 420,
          background: "#111",
          border: "1px solid #2a2a2a",
          borderRadius: 16,
          padding: 32,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Sparkles style={{ width: 18, height: 18, color: "#22c55e" }} />
            <h2 style={{ fontSize: 16, fontWeight: 700, color: "#fafafa" }}>New Project</h2>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              border: "none",
              background: "transparent",
              color: "#555",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#888", marginBottom: 8 }}>
              Name
            </label>
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Adani Q2-FY26 Analysis"
              style={{
                width: "100%",
                background: "#0a0a0a",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                padding: "12px 16px",
                fontSize: 14,
                color: "#fafafa",
                outline: "none",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "#22c55e"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#2a2a2a"; }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#888", marginBottom: 8 }}>
              System Prompt <span style={{ color: "#444" }}>(optional)</span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Custom instructions for the AI..."
              rows={3}
              style={{
                width: "100%",
                background: "#0a0a0a",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                padding: "12px 16px",
                fontSize: 14,
                color: "#fafafa",
                outline: "none",
                resize: "none",
                fontFamily: "inherit",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "#22c55e"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#2a2a2a"; }}
            />
          </div>

          <button
            type="submit"
            disabled={!name.trim() || loading}
            style={{
              width: "100%",
              padding: "12px 0",
              background: name.trim() ? "#22c55e" : "#222",
              color: name.trim() ? "black" : "#555",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 700,
              border: "none",
              cursor: name.trim() ? "pointer" : "not-allowed",
              transition: "all 0.2s ease",
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "Creating..." : "Create Project"}
          </button>
          {error && (
            <p style={{ marginTop: 12, color: "#ef4444", fontSize: 12, lineHeight: 1.5 }}>
              {error}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
