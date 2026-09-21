import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import type { LiveNormalizeResponse } from "../types";

type DisambiguationResult = {
  refinedText: string;
  disambiguations: { abbr: string; chosen: string; confidence: number; reason: string }[];
  confidence: number;
  fromCache: boolean;
};

type UseAIDisambiguationParams = {
  data: LiveNormalizeResponse | null;
  token: string | null;
  enabled: boolean;
};

const DEBOUNCE_MS = 800;

export function useAIDisambiguation({ data, token, enabled }: UseAIDisambiguationParams) {
  const [result, setResult] = useState<DisambiguationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    controllerRef.current?.abort();
    controllerRef.current = null;

    if (!enabled || !token || !data) {
      setResult(null);
      setIsLoading(false);
      return;
    }

    const hasAmbiguities = data.ambiguities.length > 0;
    const hasDiacriticChanges = data.diacriticApplied && (data.diacriticChanges?.length ?? 0) > 0;

    if (!hasAmbiguities && !hasDiacriticChanges) {
      setResult(null);
      setIsLoading(false);
      return;
    }

    const ambiguityInputs = data.ambiguities.map((a) => ({
      abbr: a.abbr,
      options: a.options,
    }));

    timerRef.current = setTimeout(() => {
      const controller = new AbortController();
      controllerRef.current = controller;
      setIsLoading(true);

      api
        .disambiguate(token, data.primaryOutput, ambiguityInputs, controller.signal)
        .then((response) => {
          if (!controller.signal.aborted) {
            setResult(response);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setResult(null);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
    // Depend on ``data`` itself so the effect reacts to any content change in
    // the ambiguity list, not just its length.
  }, [data, token, enabled]);

  return { result, isLoading };
}
