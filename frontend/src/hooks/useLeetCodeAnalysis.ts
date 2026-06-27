"use client";

import { evaluateLeetCode } from "@/lib/api";
import type { LeetCodeAnalysis } from "@/lib/types";
import { useCallback, useState } from "react";

export type LeetCodeStatus = "idle" | "loading" | "success" | "error";

export interface UseLeetCodeAnalysis {
  status: LeetCodeStatus;
  data: LeetCodeAnalysis | null;
  error: string | null;
  analyze: (url: string) => Promise<void>;
  reset: () => void;
}

/**
 * Encapsulates the LeetCode evaluation request lifecycle: loading, success,
 * and error states. Keeps the network call out of the rendering components.
 */
export function useLeetCodeAnalysis(): UseLeetCodeAnalysis {
  const [status, setStatus] = useState<LeetCodeStatus>("idle");
  const [data, setData] = useState<LeetCodeAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (url: string) => {
    setStatus("loading");
    setError(null);
    try {
      const result = await evaluateLeetCode(url);
      setData(result);
      setStatus("success");
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "LeetCode analysis failed");
      setStatus("error");
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setData(null);
    setError(null);
  }, []);

  return { status, data, error, analyze, reset };
}
