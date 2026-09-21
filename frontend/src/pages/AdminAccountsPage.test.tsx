import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AuthContext } from "../auth/AuthContext";
import { api } from "../lib/api";
import { AdminAccountsPage } from "./AdminAccountsPage";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");

  return {
    ...actual,
    api: {
      ...actual.api,
      listUsers: vi.fn(),
      deleteUser: vi.fn(),
    },
  };
});

describe("AdminAccountsPage", () => {
  it("does not offer a delete action for admin accounts", async () => {
    vi.mocked(api.listUsers).mockResolvedValue([
      {
        id: "admin-1",
        username: "admin_main",
        email: "admin@example.com",
        roles: ["admin"],
        is_active: true,
        created_at: "2026-04-01T00:00:00+00:00",
        updated_at: "2026-04-01T00:00:00+00:00",
      },
      {
        id: "user-1",
        username: "demo_user_01",
        email: "demo@example.com",
        roles: ["user"],
        is_active: true,
      },
    ]);
    render(
      <AuthContext.Provider
        value={{
          token: "token-1",
          user: {
            id: "admin-1",
            username: "admin_main",
            email: "admin@example.com",
            roles: ["admin"],
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
          <AdminAccountsPage />
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(await screen.findByText("Thông tin tài khoản")).toBeInTheDocument();
    expect(screen.getByText("Tài khoản admin không thể xóa")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Xóa tài khoản" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Lịch sử của/)).not.toBeInTheDocument();
  });
});
