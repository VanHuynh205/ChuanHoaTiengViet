import { act, renderHook } from "@testing-library/react";
import { api } from "../lib/api";
import { useDictionaryRevision } from "./useDictionaryRevision";

vi.mock("../lib/api", () => ({ api: { dictionaryRevision: vi.fn() } }));

it("refreshes two open sessions when another session changes the dictionary", async () => {
  vi.useFakeTimers();
  let revision = 1;
  vi.mocked(api.dictionaryRevision).mockImplementation(async () => ({ revision }));
  const first = renderHook(() => useDictionaryRevision("user-one"));
  const second = renderHook(() => useDictionaryRevision("user-two"));
  try {
    await act(async () => {});
    expect(first.result.current).toBe(1);
    expect(second.result.current).toBe(1);
    revision = 2;
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(first.result.current).toBe(2);
    expect(second.result.current).toBe(2);
  } finally {
    first.unmount();
    second.unmount();
    vi.useRealTimers();
  }
});
