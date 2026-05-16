// hooks/useVoice.ts
// Manages both voice input (Web Speech API) and voice output (TTS)
"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// ── Web Speech API type shims (not in lib.dom.d.ts for all targets) ──────────
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    SpeechRecognition: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    webkitSpeechRecognition: any;
  }
}

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

// ── Types ────────────────────────────────────────────────────────────────────

export type VoiceInputState = "idle" | "listening" | "processing" | "error";
export type VoiceOutputState = "idle" | "speaking" | "paused";

interface UseVoiceOptions {
  /** Called when speech recognition produces a final transcript */
  onTranscript: (text: string) => void;
  /** Language for speech recognition (default: "en-US") */
  lang?: string;
}

interface UseVoiceReturn {
  // Input
  inputState: VoiceInputState;
  startListening: () => void;
  stopListening: () => void;
  interimTranscript: string;
  inputError: string | null;
  isSupported: boolean;

  // Output
  outputState: VoiceOutputState;
  speak: (text: string) => void;
  stopSpeaking: () => void;
  pauseSpeaking: () => void;
  resumeSpeaking: () => void;
}

// Strip markdown for cleaner TTS
function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, "") // code blocks
    .replace(/`[^`]+`/g, "")        // inline code
    .replace(/#{1,6}\s+/g, "")      // headings
    .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
    .replace(/\*([^*]+)\*/g, "$1")     // italic
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
    .replace(/\[p\d+:c\d+\]/g, "")   // citation markers
    .replace(/^\s*[-*+]\s+/gm, "")   // list markers
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function useVoice({ onTranscript, lang = "en-US" }: UseVoiceOptions): UseVoiceReturn {
  const [inputState, setInputState] = useState<VoiceInputState>("idle");
  const [outputState, setOutputState] = useState<VoiceOutputState>("idle");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const [isSupported, setIsSupported] = useState(false);
  useEffect(() => {
    setIsSupported(
      typeof window !== "undefined" &&
        ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)
    );
  }, []);

  // ── Speech Recognition (Input) ────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (!isSupported) {
      setInputError("Speech recognition is not supported in this browser. Try Chrome.");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setInputState("listening");
      setInputError(null);
      setInterimTranscript("");
    };

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          final += r[0].transcript;
        } else {
          interim += r[0].transcript;
        }
      }
      setInterimTranscript(interim);
      if (final.trim()) {
        setInputState("processing");
        onTranscript(final.trim());
        setInterimTranscript("");
      }
    };

    recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
      const msgs: Record<string, string> = {
        "not-allowed": "Microphone access denied. Please allow microphone in browser settings.",
        "no-speech": "No speech detected. Please try again.",
        "aborted": "",
        "network": "Network error. Check your connection.",
      };
      const msg = msgs[e.error] ?? `Recognition error: ${e.error}`;
      if (msg) setInputError(msg);
      setInputState(e.error === "aborted" ? "idle" : "error");
    };

    recognition.onend = () => {
      setInputState((s) => (s === "processing" ? "processing" : "idle"));
      setInterimTranscript("");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [isSupported, lang, onTranscript]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setInputState("idle");
    setInterimTranscript("");
  }, []);

  // ── Speech Synthesis (Output) ─────────────────────────────────────────────
  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const clean = stripMarkdown(text);
    if (!clean) return;

    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Prefer a natural-sounding voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(
      (v) =>
        (v.name.includes("Google") || v.name.includes("Neural") || v.name.includes("Premium")) &&
        v.lang.startsWith(lang.split("-")[0])
    ) || voices.find((v) => v.lang.startsWith(lang.split("-")[0]));
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => setOutputState("speaking");
    utterance.onend = () => setOutputState("idle");
    utterance.onerror = () => setOutputState("idle");
    utterance.onpause = () => setOutputState("paused");
    utterance.onresume = () => setOutputState("speaking");

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, [lang]);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setOutputState("idle");
  }, []);

  const pauseSpeaking = useCallback(() => {
    window.speechSynthesis?.pause();
    setOutputState("paused");
  }, []);

  const resumeSpeaking = useCallback(() => {
    window.speechSynthesis?.resume();
    setOutputState("speaking");
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  return {
    inputState,
    startListening,
    stopListening,
    interimTranscript,
    inputError,
    isSupported,
    outputState,
    speak,
    stopSpeaking,
    pauseSpeaking,
    resumeSpeaking,
  };
}
