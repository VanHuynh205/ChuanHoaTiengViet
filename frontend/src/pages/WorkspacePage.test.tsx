import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthContext } from "../auth/AuthContext";
import { AppShell } from "../components/AppShell";
import { api } from "../lib/api";
import { AdminDictionaryPage } from "./AdminDictionaryPage";
import { WorkspacePage } from "./WorkspacePage";

const liveNormalizeState = vi.hoisted(() => ({
  data: {
    primaryOutput: "hom nay di dang ky",
    variants: [],
    ambiguities: [],
    pendingSubmissions: [],
    warnings: [],
    errorTypes: ["ABBREVIATION"],
    latencyMs: 12,
  } as import("../types").LiveNormalizeResponse,
}));

vi.mock("../hooks/useLiveNormalize", () => ({
  useLiveNormalize: () => ({
    data: liveNormalizeState.data,
    isLoading: false,
    isSyncing: false,
    error: null,
  }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");

  return {
    ...actual,
    api: {
      ...actual.api,
      addMeaning: vi.fn().mockResolvedValue({ status: "APPROVED" }),
      recordHistory: vi.fn().mockResolvedValue({
        id: "history-1",
        input_text: "hn di dk",
        output_text: "hom nay di dang ky",
        error_types: ["ABBREVIATION"],
        from_cache: false,
        domain: "general",
        source_kind: "web_live",
      }),
    },
  };
});

function renderWorkspace(roles: string[] = ["user"]) {
  return render(
    <AuthContext.Provider
      value={{
        token: "token-1",
        user: {
          id: "user-1",
          username: "demo_user_01",
          email: "demo@example.com",
          roles,
          is_active: true,
        },
        isBootstrapping: false,
        isAuthenticated: true,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<WorkspacePage />} />
            <Route path="dictionary" element={<AdminDictionaryPage />} />
            <Route path="history" element={<div>history page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("WorkspacePage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    liveNormalizeState.data = {
      primaryOutput: "hom nay di dang ky",
      variants: [],
      ambiguities: [],
      pendingSubmissions: [],
      warnings: [],
      errorTypes: ["ABBREVIATION"],
      latencyMs: 12,
    };
    vi.clearAllMocks();
  });

  it("keeps draft text across route changes and only saves when leaving the workspace", async () => {
    renderWorkspace();

    const editor = await screen.findByTestId("live-input-editor");
    fireEvent.change(editor, { target: { value: "hn di dk" } });

    expect(api.recordHistory).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("nav-history"));

    await waitFor(() => expect(api.recordHistory).toHaveBeenCalledTimes(1));
    expect(api.recordHistory).toHaveBeenCalledWith(
      "token-1",
      expect.objectContaining({
        inputText: "hn di dk",
        outputText: null,
        sourceKind: "web_live_partial",
      }),
      expect.anything(),
    );
    fireEvent.click(screen.getByTestId("nav-workspace"));

    expect(await screen.findByDisplayValue("hn di dk")).toBeInTheDocument();
  });

});
