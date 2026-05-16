"use client";

import { useCallback } from "react";

const UNICODE_RANGES: [RegExp, string][] = [
  [/[\u0900-\u097F]/, "hi"],  // Devanagari (Hindi)
  [/[\u0A80-\u0AFF]/, "gu"],  // Gujarati
  [/[\u0600-\u06FF]/, "ar"],  // Arabic
  [/[\u4E00-\u9FFF]/, "zh"],  // Chinese CJK
  [/[\u3040-\u309F]/, "ja"],  // Hiragana (Japanese)
  [/[\u0B80-\u0BFF]/, "ta"],  // Tamil
  [/[\u0980-\u09FF]/, "bn"],  // Bengali
];

export function useLanguageDetect() {
  const detect = useCallback((text: string): string => {
    for (const [regex, code] of UNICODE_RANGES) {
      if (regex.test(text)) return code;
    }
    return "en";
  }, []);

  return { detect };
}
