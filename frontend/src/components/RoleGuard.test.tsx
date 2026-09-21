import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthContext } from "../auth/AuthContext";
import { RoleGuard } from "./RoleGuard";

function renderWithAuth(roles: string[]) {
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
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/" element={<div>workspace</div>} />
          <Route
            path="/admin"
            element={
              <RoleGuard role="admin">
                <div>admin-only</div>
              </RoleGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("RoleGuard", () => {
  it("redirects non-admin users away from admin pages", async () => {
    renderWithAuth(["user"]);
    expect(await screen.findByText("workspace")).toBeInTheDocument();
  });

  it("renders admin pages for admin users", async () => {
    renderWithAuth(["admin"]);
    expect(await screen.findByText("admin-only")).toBeInTheDocument();
  });
});
