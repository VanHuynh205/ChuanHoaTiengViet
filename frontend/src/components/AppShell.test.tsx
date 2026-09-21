import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthContext } from "../auth/AuthContext";
import { AppShell } from "./AppShell";

function renderShell(roles: string[]) {
  return render(
    <AuthContext.Provider
      value={{
        token: "token-1",
        user: {
          id: "user-1",
          username: "demo",
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
      <MemoryRouter initialEntries={["/history"]}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<div>workspace</div>} />
            <Route path="history" element={<div>history</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("AppShell", () => {
  it("hides admin navigation for regular users", async () => {
    renderShell(["user"]);

    expect(await screen.findByTestId("nav-history")).toBeInTheDocument();
    expect(screen.getByTestId("nav-dictionary")).toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-accounts")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-moderation")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-dictionary")).not.toBeInTheDocument();
  });

  it("shows admin navigation for admin users", async () => {
    renderShell(["admin"]);

    expect(await screen.findByTestId("nav-dictionary")).toBeInTheDocument();
    expect(await screen.findByTestId("nav-admin-accounts")).toBeInTheDocument();
    expect(screen.getByTestId("nav-admin-moderation")).toBeInTheDocument();
    expect(screen.queryByTestId("nav-admin-dictionary")).not.toBeInTheDocument();
  });
});
