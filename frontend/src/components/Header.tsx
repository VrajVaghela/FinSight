"use client";

import { useState } from "react";
import {
  ShieldCheck,
  Monitor,
  FileDown,
  Activity,
  SlidersHorizontal,
  PanelRightOpen,
  PanelRightClose,
} from "lucide-react";

interface HeaderProps {
  projectName?: string;
  onToggleDebug?: () => void;
  debugOpen?: boolean;
}

export default function Header({ projectName, onToggleDebug, debugOpen }: HeaderProps) {
  const headerButtons = [
    { icon: Monitor, tooltip: "Terminal" },
    { icon: FileDown, tooltip: "Export" },
    { icon: Activity, tooltip: "Activity" },
    { icon: SlidersHorizontal, tooltip: "Settings" },
  ];

  return (
    <header
      className="animate-fade-down"
      style={{
        height: 52,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        borderBottom: "1px solid #1e1e1e",
        background: "#111111",
        flexShrink: 0,
      }}
    >
      {/* Left */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 700,
            color: "#22c55e",
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.15)",
            padding: "4px 12px",
            borderRadius: 99,
          }}
        >
          <ShieldCheck style={{ width: 12, height: 12 }} />
          <span>v2.5</span>
        </div>

        {projectName && (
          <>
            <div style={{ width: 1, height: 20, background: "#2a2a2a" }} />
            <span style={{ fontSize: 13, color: "#888", fontWeight: 500 }}>
              {projectName}
            </span>
          </>
        )}
      </div>

      {/* Right */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {onToggleDebug && (
          <button
            onClick={onToggleDebug}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid",
              borderColor: debugOpen ? "rgba(34,197,94,0.3)" : "#2a2a2a",
              background: debugOpen ? "rgba(34,197,94,0.06)" : "transparent",
              color: debugOpen ? "#22c55e" : "#666",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {debugOpen ? (
              <PanelRightClose style={{ width: 14, height: 14 }} />
            ) : (
              <PanelRightOpen style={{ width: 14, height: 14 }} />
            )}
            Debug
          </button>
        )}

        {headerButtons.map((btn) => (
          <button
            key={btn.tooltip}
            title={btn.tooltip}
            style={{
              width: 32,
              height: 32,
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
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#1a1a1a";
              e.currentTarget.style.color = "#aaa";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "#555";
            }}
          >
            <btn.icon style={{ width: 16, height: 16 }} />
          </button>
        ))}
      </div>
    </header>
  );
}
