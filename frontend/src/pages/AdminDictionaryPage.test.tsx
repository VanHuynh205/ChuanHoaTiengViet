import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AuthContext } from "../auth/AuthContext";
import { api } from "../lib/api";
import { AdminDictionaryPage } from "./AdminDictionaryPage";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");

  return {
    ...actual,
    api: {
      ...actual.api,
      listAbbreviations: vi.fn(),
      saveAbbreviation: vi.fn(),
      dictionarySyncStatus: vi.fn(),
      retryDictionaryExport: vi.fn(),
    },
  };
});

function renderDictionary(roles: string[]) {
  return render(
    <AuthContext.Provider
      value={{
        token: "token-1",
        user: {
          id: roles.includes("admin") ? "admin-1" : "user-1",
          username: roles.includes("admin") ? "admin_main" : "demo_user_01",
          email: roles.includes("admin") ? "admin@example.com" : "demo@example.com",
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
      <MemoryRouter>
        <AdminDictionaryPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("AdminDictionaryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.dictionarySyncStatus).mockResolvedValue({ revision: 1, status: "synced" });
    vi.mocked(api.listAbbreviations).mockResolvedValue([
      {
        id: "abbr-dk",
        abbr: "dk",
        expanded: "dang ky",
        alternative_expansions: ["dung khong"],
        domain: "general",
        source: "sql_server",
        approved_by: "admin",
        created_at: null,
      },
    ]);
  });

  it("loads dictionary entries and saves global edits for admins", async () => {
    vi.mocked(api.saveAbbreviation).mockResolvedValue({
      id: "abbr-dk",
      abbr: "dk",
      expanded: "dang ky moi",
      alternative_expansions: ["dung khong", "duoc khong"],
      domain: "general",
      source: "admin_dictionary",
      approved_by: "admin_main",
      created_at: null,
    });

    renderDictionary(["admin"]);

    expect(await screen.findByText("Danh sách từ viết tắt")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /dk/i }));
    fireEvent.change(screen.getByTestId("dictionary-expanded-input"), {
      target: { value: "dang ky moi" },
    });
    fireEvent.change(screen.getByTestId("dictionary-alternatives-input"), {
      target: { value: "dung khong\nduoc khong" },
    });
    fireEvent.click(screen.getByTestId("dictionary-submit"));

    await waitFor(() =>
      expect(api.saveAbbreviation).toHaveBeenCalledWith(
        "token-1",
        "dk",
        "dang ky moi",
        ["dung khong", "duoc khong"],
        "general",
      ),
    );
    expect(await screen.findByText('Đã lưu mục từ "dk".')).toBeInTheDocument();
  });

  it("reads a persisted export failure and retries without resaving the SQL edit", async () => {
    vi.mocked(api.dictionarySyncStatus).mockResolvedValue({ revision: 2, status: "export_failed" });
    vi.mocked(api.retryDictionaryExport).mockResolvedValue({ revision: 3, status: "synced" });
    renderDictionary(["admin"]);
    expect(await screen.findByText(/Đã lưu vào SQL/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thử đồng bộ JSON lại" }));
    await waitFor(() => expect(api.retryDictionaryExport).toHaveBeenCalledWith("token-1"));
    await waitFor(() => expect(screen.queryByText(/Đã lưu vào SQL/)).not.toBeInTheDocument());
    expect(api.saveAbbreviation).not.toHaveBeenCalled();
  });

  it("renders shared abbreviations from every domain with primary and alternative meanings", async () => {
    vi.mocked(api.listAbbreviations).mockResolvedValue([
      {
        id: "abbr-dk",
        abbr: "dk",
        expanded: "dang ky",
        alternative_expansions: ["dung khong"],
        domain: "general",
        source: "sql_server",
        approved_by: "admin",
        created_at: null,
      },
      {
        id: "json-vc",
        abbr: "vc",
        expanded: "viec",
        alternative_expansions: ["vo chong", "van chuyen"],
        domain: "text_normalization",
        source: "json_seed",
        approved_by: "seed",
        created_at: null,
      },
    ]);

    renderDictionary(["user"]);

    expect(await screen.findByText("viec")).toBeInTheDocument();
    expect(screen.getByText(/vo chong/)).toBeInTheDocument();
    expect(screen.getByText(/van chuyen/)).toBeInTheDocument();
    expect(api.listAbbreviations).toHaveBeenCalledWith("token-1");
  });

  it("saves edits back to the selected abbreviation domain when abbreviations are duplicated", async () => {
    vi.mocked(api.listAbbreviations).mockResolvedValue([
      {
        id: "vc-general",
        abbr: "vc",
        expanded: "viec",
        alternative_expansions: [],
        domain: "general",
        source: "sql_server",
        approved_by: "admin",
        created_at: null,
      },
      {
        id: "vc-text",
        abbr: "vc",
        expanded: "vo chong",
        alternative_expansions: [],
        domain: "text_normalization",
        source: "json_seed",
        approved_by: "seed",
        created_at: null,
      },
    ]);
    vi.mocked(api.saveAbbreviation).mockResolvedValue({
      id: "vc-text",
      abbr: "vc",
      expanded: "vo chong moi",
      alternative_expansions: [],
      domain: "text_normalization",
      source: "admin_dictionary",
      approved_by: "admin_main",
      created_at: null,
    });

    renderDictionary(["admin"]);

    const vcEntries = await screen.findAllByRole("button", { name: /vc/i });
    fireEvent.click(vcEntries[1]);
    fireEvent.change(screen.getByTestId("dictionary-expanded-input"), {
      target: { value: "vo chong moi" },
    });
    fireEvent.click(screen.getByTestId("dictionary-submit"));

    await waitFor(() =>
      expect(api.saveAbbreviation).toHaveBeenCalledWith(
        "token-1",
        "vc",
        "vo chong moi",
        [],
        "text_normalization",
      ),
    );
  });

  it("keeps regular users in read-only dictionary mode", async () => {
    renderDictionary(["user"]);

    expect(await screen.findByText("Danh sách từ viết tắt")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /dk/i }));
    expect(screen.getByTestId("dictionary-readonly")).toBeInTheDocument();
    expect(screen.queryByTestId("dictionary-expanded-input")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dictionary-submit")).not.toBeInTheDocument();
    expect(api.saveAbbreviation).not.toHaveBeenCalled();
  });
});
