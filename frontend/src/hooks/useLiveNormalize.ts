import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "../lib/api";
import type { LiveInputMethod, LiveNormalizeResponse } from "../types";

type UseLiveNormalizeParams = {
  text: string;
  token: string | null;
  resolutionOverrides: Record<string, string>;
  inputMethod: LiveInputMethod;
  allowAi?: boolean;
  dictionaryVersion?: number;
};

const TYPING_DEBOUNCE_MS = 120;
const AI_IDLE_MS = 700;

export function clearResponseCache() {
  window.dispatchEvent(new Event("dictionary-updated"));
}

export function useLiveNormalize({
  text, token, resolutionOverrides, inputMethod, allowAi = false, dictionaryVersion = 0,
}: UseLiveNormalizeParams) {
  const [state, setState] = useState<{
    key: string; data: LiveNormalizeResponse | null; loading: boolean; syncing: boolean; error: string | null;
  }>({ key: "", data: null, loading: false, syncing: false, error: null });
  const revision = useRef(0);
  const key = JSON.stringify({ text, token, resolutionOverrides, inputMethod, allowAi, dictionaryVersion });

  useEffect(() => {
    const version = ++revision.current;
    const controller = new AbortController();
    let idleTimer: number | undefined;
    let releaseIdle: (() => void) | undefined;
    const valid = () => !controller.signal.aborted && version === revision.current;
    const stamp = (response: LiveNormalizeResponse, pending = false): LiveNormalizeResponse => ({
      ...response, inputText: text, inputVersion: version,
      normalizationPhase: pending ? "ai_pending" : "complete",
      ...(pending ? { semanticStatus: "not_checked" as const, semanticStatusReason: "waiting_for_ai" } : {}),
    });
    const publish = (data: LiveNormalizeResponse, syncing: boolean) => {
      if (valid()) setState({ key, data, loading: false, syncing, error: null });
    };
    if (!token || !text.trim()) {
      setState({ key, data: null, loading: false, syncing: false, error: null });
      return () => controller.abort();
    }
    setState({ key, data: null, loading: true, syncing: false, error: null });
    // Computed once: `text` is fixed for this effect run and both the AI-idle
    // timer and the dataset callback must agree on the same boundary test.
    const endsAtSentenceBoundary = /[.!?…]["')\]]?\s*$/.test(text);
    const aiReady = new Promise<void>((resolve) => {
      releaseIdle = resolve;
      idleTimer = window.setTimeout(
        resolve,
        inputMethod === "paste" || endsAtSentenceBoundary ? 0 : AI_IDLE_MS,
      );
    });
    const datasetTimer = window.setTimeout(async () => {
      let dataset: LiveNormalizeResponse | null = null;
      try {
        dataset = await api.normalizeLive(text, resolutionOverrides, inputMethod, token, false, controller.signal);
        if (!valid()) return;
        // A paused keystroke is not a stable semantic review point. Sending an
        // AI request after every short pause quickly exhausts the shared
        // per-user budget while the user is still composing a sentence. Paste
        // and explicit sentence boundaries are stable review points.
        const needsAi = allowAi && (inputMethod === "paste" || endsAtSentenceBoundary);
        publish(stamp(dataset, needsAi), needsAi);
        if (!needsAi) {
          return;
        }
        await aiReady;
        if (!valid()) return;
        const response = await api.normalizeLive(text, resolutionOverrides, inputMethod, token, true, controller.signal,
          (partial) => {
            dataset = partial;
            publish({ ...stamp(partial), normalizationPhase: "ai_pending" }, true);
          });
        if (!valid()) return;
        const finished = stamp(response);
        publish(finished, false);
      } catch (error: unknown) {
        if (!valid()) return;
        setState({ key, data: dataset ? stamp({ ...dataset, semanticStatus: dataset.semanticVerifiedChunks ? "partial" : "error", semanticStatusReason: "provider_error" }) : null,
          loading: false, syncing: false,
          error: error instanceof ApiError ? error.message : "Khong the dong bo ket qua hien tai." });
      }
    }, inputMethod === "paste" ? 0 : TYPING_DEBOUNCE_MS);
    return () => {
      controller.abort();
      window.clearTimeout(datasetTimer);
      window.clearTimeout(idleTimer);
      releaseIdle?.();
    };
    // key includes every request input; object identity must not restart requests.
  }, [key]);

  const current = state.key === key;
  return {
    data: current ? state.data : null,
    isLoading: current ? state.loading : Boolean(token && text.trim()),
    isSyncing: current && state.syncing,
    error: current ? state.error : null,
  };
}
