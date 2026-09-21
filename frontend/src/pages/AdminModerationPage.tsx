import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { AbbreviationDetailDrawer } from "../components/AbbreviationDetailDrawer";
import { AdminPendingTable } from "../components/AdminPendingTable";
import { AdminAIMeanings } from "../components/AdminAIMeanings";
import { api, ApiError } from "../lib/api";
import type { ApprovedAbbreviation, PendingAbbreviation } from "../types";

export function AdminModerationPage() {
  const { token } = useAuth();
  const [pendingItems, setPendingItems] = useState<PendingAbbreviation[]>([]);
  const [selectedPending, setSelectedPending] = useState<PendingAbbreviation | null>(null);
  const [selectedAbbreviation, setSelectedAbbreviation] = useState<ApprovedAbbreviation | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadPending() {
    if (!token) {
      return;
    }

    try {
      const pendingResponse = await api.getPending(token);
      setPendingItems(pendingResponse);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Không tải được danh sách kiểm duyệt.");
    }
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const pendingResponse = await api.getPending(token);
        if (cancelled) {
          return;
        }
        setPendingItems(pendingResponse);
      } catch (caughtError) {
        if (cancelled) {
          return;
        }
        setError(
          caughtError instanceof ApiError
            ? caughtError.message
            : "Không tải được danh sách kiểm duyệt.",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleView(pending: PendingAbbreviation) {
    if (!token) {
      return;
    }

    setSelectedPending(pending);
    try {
      const detail = await api.getAbbreviation(pending.abbr, token);
      setSelectedAbbreviation(detail);
    } catch {
      setSelectedAbbreviation(null);
    }
  }

  async function handleApprove(pending: PendingAbbreviation) {
    if (!token) {
      return;
    }

    try {
      const approved = await api.approvePending(
        pending.id,
        token,
        pending.suggested ?? pending.suggested_meanings[0],
      );
      setError(null);
      await loadPending();
      if (approved?.dictionary_sync?.status === "export_failed") {
        setError("Đã duyệt trong SQL nhưng JSON chưa đồng bộ. Mở trang Từ điển để thử đồng bộ lại.");
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Không thể duyệt mục pending vào lúc này.",
      );
    }
  }

  async function handleReject(pending: PendingAbbreviation) {
    if (!token) {
      return;
    }

    try {
      await api.rejectPending(pending.id, token, "Rejected from admin moderation page.");
      setError(null);
      await loadPending();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Không thể từ chối mục pending vào lúc này.",
      );
    }
  }

  return (
    <section className="page-stack">
      <header className="page-hero">
        <div>
          <p className="eyebrow">Quản trị</p>
          <h1>Kiểm duyệt pending</h1>
          <p className="page-hero__copy">
            Admin kiểm tra chi tiết gợi ý và quyết định duyệt/từ chối.
          </p>
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      <AdminPendingTable
        pendingItems={pendingItems}
        onApprove={(pending) => void handleApprove(pending)}
        onReject={(pending) => void handleReject(pending)}
        onView={(pending) => void handleView(pending)}
      />
      <AdminAIMeanings token={token} />

      {selectedPending ? (
        <div className="notice notice--info">
          <p className="panel__label">Chi tiết chờ duyệt</p>
          <h3>{selectedPending.abbr}</h3>
          <p>{selectedPending.suggested_meanings.join(", ") || "Chưa có nghĩa được nhập."}</p>
        </div>
      ) : null}

      <AbbreviationDetailDrawer detail={selectedAbbreviation} onClose={() => setSelectedAbbreviation(null)} />
    </section>
  );
}
