import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { HistoryList } from "../components/HistoryList";
import { api, ApiError } from "../lib/api";
import type { NormalizationHistoryEntry } from "../types";

export function HistoryPage() {
  const { token, user } = useAuth();
  const [entries, setEntries] = useState<NormalizationHistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    api
      .listMyHistory(token)
      .then((response) => {
        setEntries(response);
        setError(null);
      })
      .catch((caughtError) => {
        setError(caughtError instanceof ApiError ? caughtError.message : "Không tải được lịch sử chuẩn hóa.");
      });
  }, [token]);

  async function handleDeleteEntry(entry: NormalizationHistoryEntry) {
    if (!token) {
      return;
    }
    if (!window.confirm("Bạn có chắc muốn xóa bản ghi lịch sử này không?")) {
      return;
    }

    try {
      setDeletingEntryId(entry.id);
      await api.deleteHistory(token, entry.id);
      setEntries((current) => current.filter((candidate) => candidate.id !== entry.id));
      setError(null);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Không thể xóa bản ghi lịch sử đã chọn.");
    } finally {
      setDeletingEntryId(null);
    }
  }

  return (
    <section className="page-stack">
      <header className="page-hero">
        <div>
          <p className="eyebrow">Cá nhân</p>
          <h1>Lịch sử chuẩn hóa</h1>
          <p className="page-hero__copy">
            Theo dõi các lần chuẩn hóa gần đây của tài khoản <strong>{user?.username}</strong> để kiểm tra đầu vào, đầu ra
            và trạng thái xử lý.
          </p>
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      <HistoryList
        emptyMessage="Tài khoản này chưa có bản ghi chuẩn hóa nào được lưu."
        entries={entries}
        title="Lịch sử của bạn"
        deletingEntryId={deletingEntryId}
        onDelete={handleDeleteEntry}
      />
    </section>
  );
}
