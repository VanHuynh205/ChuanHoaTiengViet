import { act, renderHook, waitFor } from "@testing-library/react";

import { clearResponseCache, useLiveNormalize } from "./useLiveNormalize";

const liveResponse = {
  primaryOutput: "normalized text",
  variants: [
    {
      id: "variant-0",
      output: "normalized text",
      resolutions: [{ ambiguity_id: "dk:0", meaning: "dang ky" }],
      isPrimary: true,
    },
  ],
  ambiguities: [],
  pendingSubmissions: [],
  warnings: [],
  errorTypes: ["ABBR"],
  latencyMs: 12,
};

describe("useLiveNormalize", () => {
  it("reviews the full text with AI even when the dataset reports no ambiguities", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_input, init) => {
      const body = JSON.parse(String(init?.body));
      return Promise.resolve(new Response(JSON.stringify({ ...liveResponse,
        semanticStatus: body.allowAI ? "verified" : "not_needed",
        primaryOutput: body.allowAI ? "Nhớ nhắc lịch hẹn." : "Nhớ nhạc lịch hẹn.",
      })));
    }));
    const { result } = renderHook(() => useLiveNormalize({ text: "Nhớ nhạc lịch hẹn.", token: "full-review",
      resolutionOverrides: {}, inputMethod: "paste", allowAi: true }));
    await waitFor(() => expect(result.current.data?.primaryOutput).toBe("Nhớ nhắc lịch hẹn."));
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  beforeEach(() => {
    clearResponseCache();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("shows dataset before slow AI and rejects a late result after editing", async () => {
    let finishAi: ((response: Response) => void) | undefined;
    vi.mocked(fetch).mockImplementation((_input, init) => {
      const body = JSON.parse(String(init?.body));
      if (body.allowAI) return new Promise<Response>((resolve) => { finishAi = resolve; });
      return Promise.resolve(new Response(JSON.stringify({ ...liveResponse,
        primaryOutput: `dataset: ${body.text}`, semanticStatus: "not_checked" })));
    });
    const { result, rerender } = renderHook(({ text }) => useLiveNormalize({
      text, token: "progress-user", resolutionOverrides: {}, inputMethod: "typing", allowAi: true,
    }), { initialProps: { text: "dk." } });
    await waitFor(() => expect(result.current.data?.primaryOutput).toBe("dataset: dk."));
    expect(result.current.isSyncing).toBe(true);
    await waitFor(() => expect(finishAi).toBeDefined());
    rerender({ text: "dk moi" });
    expect(result.current.data).toBeNull();
    await act(async () => finishAi?.(new Response(JSON.stringify({ ...liveResponse, primaryOutput: "stale AI" }))));
    await waitFor(() => expect(result.current.data?.primaryOutput).toBe("dataset: dk moi"));
    expect(result.current.data?.inputText).toBe("dk moi");
  });

  it("does not spend an AI request while typing an unfinished sentence", async () => {
    vi.mocked(fetch).mockImplementation((_input, init) => {
      const body = JSON.parse(String(init?.body));
      return Promise.resolve(new Response(JSON.stringify({
        ...liveResponse,
        primaryOutput: `dataset: ${body.text}`,
        semanticStatus: "not_checked",
      })));
    });

    const { result } = renderHook(() => useLiveNormalize({
      text: "dk dang hoc",
      token: "typing-budget",
      resolutionOverrides: {},
      inputMethod: "typing",
      allowAi: true,
    }));

    await waitFor(() => expect(result.current.data?.primaryOutput).toBe("dataset: dk dang hoc"));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string).allowAI).toBe(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps a streamed partial result when the connection ends without completion", async () => {
    vi.mocked(fetch).mockImplementation((_input, init) => {
      const body = JSON.parse(String(init?.body));
      if (!body.allowAI) return Promise.resolve(new Response(JSON.stringify({
        ...liveResponse, semanticStatus: "not_checked",
      })));
      const bytes = new TextEncoder().encode(JSON.stringify({ result: {
        ...liveResponse, primaryOutput: "Đăng ký\n\ndk", semanticStatus: "partial",
        semanticVerifiedChunks: 1, semanticTotalChunks: 2,
      }, complete: false }) + "\n");
      return Promise.resolve(new Response(new ReadableStream({ start(controller) {
        controller.enqueue(bytes.slice(0, 5));
        controller.enqueue(bytes.slice(5));
        controller.close();
      } }), { headers: { "Content-Type": "application/x-ndjson" } }));
    });
    const { result } = renderHook(() => useLiveNormalize({
      text: "dk\n\ndk", token: "stream-user", resolutionOverrides: {}, inputMethod: "paste", allowAi: true,
    }));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.data?.primaryOutput).toBe("Đăng ký\n\ndk");
    expect(result.current.data?.semanticStatus).toBe("partial");
    expect(result.current.isSyncing).toBe(false);
  });

  it("accepts a completed AI event that arrives without a trailing newline", async () => {
    vi.mocked(fetch).mockImplementation((_input, init) => {
      const body = JSON.parse(String(init?.body));
      if (!body.allowAI) return Promise.resolve(new Response(JSON.stringify({
        ...liveResponse, semanticStatus: "not_checked",
      })));
      const payload = JSON.stringify({ result: {
        ...liveResponse, primaryOutput: "Đăng ký môn học", semanticStatus: "verified",
      }, complete: true });
      const bytes = new TextEncoder().encode(payload);
      return Promise.resolve(new Response(new ReadableStream({ start(controller) {
        // Deliberately NO trailing "\n" on the final event.
        controller.enqueue(bytes.slice(0, 10));
        controller.enqueue(bytes.slice(10));
        controller.close();
      } }), { headers: { "Content-Type": "application/x-ndjson" } }));
    });
    const { result } = renderHook(() => useLiveNormalize({
      text: "dk mon hoc", token: "tail-user", resolutionOverrides: {}, inputMethod: "paste", allowAi: true,
    }));
    await waitFor(() => {
      expect(result.current.data?.primaryOutput).toBe("Đăng ký môn học");
      expect(result.current.data?.semanticStatus).toBe("verified");
    });
  });

  it("debounces rapid typing and requests only the latest text", async () => {
    const abortSignals: AbortSignal[] = [];
    vi.mocked(fetch).mockImplementation((_input, init) => {
      abortSignals.push(init?.signal as AbortSignal);
      const body = JSON.parse(init?.body as string) as { text: string };
      const response = {
        ...liveResponse,
        primaryOutput: `normalized: ${body.text}`,
      };
      return Promise.resolve(
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    const { result, rerender } = renderHook(
      ({ text }) =>
        useLiveNormalize({
          text,
          token: "token-1",
          resolutionOverrides: {},
          inputMethod: "typing",
        }),
      {
        initialProps: { text: "source one" },
      },
    );

    rerender({ text: "source two" });
    rerender({ text: "source three" });

    expect(fetch).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(result.current.data?.primaryOutput).toBe("normalized: source three");
    });

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string).inputMethod).toBe(
      "typing",
    );
    expect(abortSignals[0].aborted).toBe(false);
  });

  it("aborts an in-flight request and revalidates repeated text with the server", async () => {
    const abortSignals: Array<{ text: string; signal: AbortSignal }> = [];

    vi.mocked(fetch).mockImplementation((_input, init) => {
      const body = JSON.parse(init?.body as string) as { text: string };
      abortSignals.push({ text: body.text, signal: init?.signal as AbortSignal });
      if (body.text === "cached source text") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ...liveResponse,
              primaryOutput: "normalized: cached source text",
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        );
      }
      return new Promise<Response>(() => undefined);
    });

    const { result, rerender } = renderHook(
      ({ text }) =>
        useLiveNormalize({
          text,
          token: "token-1",
          resolutionOverrides: {},
          inputMethod: "typing",
        }),
      {
        initialProps: { text: "cached source text" },
      },
    );

    await waitFor(() => {
      expect(result.current.data?.primaryOutput).toBe("normalized: cached source text");
    });

    rerender({ text: "still running source text" });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    rerender({ text: "cached source text" });

    await waitFor(() => {
      expect(abortSignals[1].signal.aborted).toBe(true);
    });

    // The response of fetch #3 only reaches the hook state after
    // response.json() -> publish -> setState -> a React scheduler flush, which
    // is a separate task from the fetch call itself. Asserting the fetch count
    // and the published result in ONE waitFor removes the task-ordering race
    // that made this test fail ~1 in 4 full-suite runs under load.
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledTimes(3);
      expect(result.current.data?.primaryOutput).toBe("normalized: cached source text");
    });
    expect(abortSignals).toHaveLength(3);
    expect(abortSignals[0].signal.aborted).toBe(true);
    expect(abortSignals[1].text).toBe("still running source text");
  });
});
