"use client";

import { Volume2, VolumeX, Square } from "lucide-react";

interface VoiceSpeakerProps {
  text: string;
  outputState: "idle" | "speaking" | "paused";
  onSpeak: (text: string) => void;
  onStop: () => void;
}

export default function VoiceSpeaker({ text, outputState, onSpeak, onStop }: VoiceSpeakerProps) {
  const isSpeaking = outputState === "speaking" || outputState === "paused";

  return (
    <button
      type="button"
      onClick={() => (isSpeaking ? onStop() : onSpeak(text))}
      title={isSpeaking ? "Stop speaking" : "Read aloud"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 8px",
        background: isSpeaking ? "rgba(167,139,250,0.12)" : "transparent",
        border: "1px solid",
        borderColor: isSpeaking ? "rgba(167,139,250,0.3)" : "#2a2a2a",
        borderRadius: 6,
        color: isSpeaking ? "#a78bfa" : "#555",
        cursor: "pointer",
        fontSize: 11,
        fontWeight: 500,
        transition: "all 0.15s ease",
      }}
    >
      {isSpeaking ? (
        <>
          <Square size={10} style={{ fill: "#a78bfa" }} />
          <span>Stop</span>
        </>
      ) : (
        <>
          <Volume2 size={10} />
          <span>Speak</span>
        </>
      )}
    </button>
  );
}
