import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Icon, type IconName } from "./Icon";
import { BrandMark } from "./BrandMark";
import { useAuth } from "../auth/AuthContext";
import { WORKSPACE_FLUSH_EVENT } from "../lib/workspaceSession";

const workItems: { to: string; label: string; end?: boolean; testId: string; icon: IconName }[] = [
  { to: "/", label: "Làm việc", end: true, testId: "nav-workspace", icon: "document" },
  { to: "/dictionary", label: "Từ điển", testId: "nav-dictionary", icon: "book" },
  { to: "/history", label: "Lịch sử chuẩn hóa", testId: "nav-history", icon: "history" },
];

const adminItems: { to: string; label: string; testId: string; icon: IconName }[] = [
  { to: "/admin/accounts", label: "Quản lý tài khoản", testId: "nav-admin-accounts", icon: "user" },
  { to: "/admin/moderation", label: "Kiểm duyệt", testId: "nav-admin-moderation", icon: "shield" },
];

export function AppShell() {
  const { logout, user } = useAuth();
  const isAdmin = user?.roles.includes("admin");
  const location = useLocation();

  function announceWorkspaceFlush() {
    window.dispatchEvent(new Event(WORKSPACE_FLUSH_EVENT));
  }

  function handleNavigationIntent(target: string) {
    if (location.pathname !== target) {
      announceWorkspaceFlush();
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Đến nội dung chính</a>
      <aside className="app-shell__sidebar">
        <div className="app-shell__brand">
          <div className="brand-lockup"><BrandMark /><span><strong>VIỆT</strong><br />NORMALIZER</span></div>
        </div>
        <span className="app-shell__sidebar-glow" aria-hidden="true" />

        <nav className="app-shell__nav" aria-label="Điều hướng chính">
          <div className="app-shell__nav-group">
            <p className="app-shell__nav-label">Làm việc</p>
            {workItems.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) => `app-shell__nav-link${isActive ? " app-shell__nav-link--active" : ""}`}
                data-testid={item.testId}
                end={item.end}
                to={item.to}
                onClick={() => handleNavigationIntent(item.to)}
              >
                <Icon name={item.icon} /><span>{item.label}</span>
              </NavLink>
            ))}
          </div>

          {isAdmin ? (
            <div className="app-shell__nav-group">
              <p className="app-shell__nav-label">Quản trị</p>
              {adminItems.map((item) => (
                <NavLink
                  key={item.to}
                  className={({ isActive }) => `app-shell__nav-link${isActive ? " app-shell__nav-link--active" : ""}`}
                  data-testid={item.testId}
                  to={item.to}
                  onClick={() => handleNavigationIntent(item.to)}
                >
                  <Icon name={item.icon} /><span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ) : null}
        </nav>

        <div className="app-shell__account">
          <div className="app-shell__account-card">
            <span className="app-shell__avatar" aria-hidden="true">{(user?.username ?? "?").trim().charAt(0).toUpperCase()}</span>
            <div className="app-shell__account-identity">
              <p className="panel__label">Tài khoản hiện tại</p>
              <strong>{user?.username}</strong>
              <p className="app-shell__account-meta">{user?.email}</p>
              <div className="app-shell__role-list">
                {user?.roles.map((role) => (
                  <span key={role} className="app-shell__role-pill">
                    {role}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              announceWorkspaceFlush();
              void logout();
            }}
          >
            <Icon name="logout" /> Đăng xuất
          </button>
        </div>
      </aside>

      <main id="main-content" className="app-shell__content">
        <Outlet />
      </main>
    </div>
  );
}
