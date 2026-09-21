import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { api, ApiError } from "../lib/api";
import type { AuthUser } from "../types";

function formatDate(value?: string | null) {
  if (!value) {
    return "Chưa có";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function AdminAccountsPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? users[0] ?? null,
    [selectedUserId, users],
  );

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const response = await api.listUsers(token);
        if (cancelled) {
          return;
        }
        setUsers(response);
        setSelectedUserId((current) => current ?? response[0]?.id ?? null);
        setError(null);
      } catch (caughtError) {
        if (cancelled) {
          return;
        }
        setError(
          caughtError instanceof ApiError
            ? caughtError.message
            : "Không tải được danh sách tài khoản.",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleDeleteUser() {
    if (!token || !selectedUser) {
      return;
    }
    if (selectedUser.roles.includes("admin")) {
      return;
    }
    if (!window.confirm(`Bạn có chắc muốn xóa tài khoản "${selectedUser.username}" không?`)) {
      return;
    }

    try {
      await api.deleteUser(token, selectedUser.id);
      const remainingUsers = users.filter((user) => user.id !== selectedUser.id);
      setUsers(remainingUsers);
      setSelectedUserId(remainingUsers[0]?.id ?? null);
      setError(null);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Không thể xóa tài khoản đã chọn.");
    }
  }

  return (
    <section className="page-stack">
      <header className="page-hero">
        <div>
          <p className="eyebrow">Quản trị</p>
          <h1>Quản lý tài khoản</h1>
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="accounts-layout">
        <section className="panel accounts-list-panel">
          <div className="panel__header">
            <div>
              <p className="panel__label">Danh sách tài khoản</p>
              <h2>Danh sách tài khoản</h2>
            </div>
          </div>

          <div className="accounts-list">
            {users.map((user) => {
              const isSelected = user.id === selectedUser?.id;

              return (
                <button
                  key={user.id}
                  className={`accounts-list__item${isSelected ? " accounts-list__item--selected" : ""}`}
                  data-testid={`account-item-${user.id}`}
                  type="button"
                  onClick={() => setSelectedUserId(user.id)}
                >
                  <div>
                    <strong>{user.username}</strong>
                    <p>{user.email}</p>
                  </div>
                  <span>{user.roles.join(", ")}</span>
                </button>
              );
            })}
          </div>
        </section>

        <div className="accounts-detail-stack">
          <section className="panel account-detail-panel">
            <div className="panel__header">
              <div>
                <p className="panel__label">Chi tiết tài khoản</p>
                <h2>Thông tin tài khoản</h2>
              </div>
              {selectedUser ? (
                selectedUser.roles.includes("admin") ? (
                  <span className="status-pill status-pill--syncing">Tài khoản admin không thể xóa</span>
                ) : (
                  <button className="danger-button" type="button" onClick={() => void handleDeleteUser()}>
                    Xóa tài khoản
                  </button>
                )
              ) : null}
            </div>

            {selectedUser ? (
              <dl className="account-detail-grid">
                <div>
                  <dt>Tên đăng nhập</dt>
                  <dd>{selectedUser.username}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{selectedUser.email}</dd>
                </div>
                <div>
                  <dt>Vai trò</dt>
                  <dd>{selectedUser.roles.join(", ")}</dd>
                </div>
                <div>
                  <dt>Trạng thái</dt>
                  <dd>{selectedUser.is_active ? "Đang hoạt động" : "Đã khóa"}</dd>
                </div>
                <div>
                  <dt>Ngày tạo</dt>
                  <dd>{formatDate(selectedUser.created_at)}</dd>
                </div>
                <div>
                  <dt>Cập nhật gần nhất</dt>
                  <dd>{formatDate(selectedUser.updated_at)}</dd>
                </div>
              </dl>
            ) : (
              <div className="page-state">Chưa có tài khoản nào để hiển thị.</div>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
