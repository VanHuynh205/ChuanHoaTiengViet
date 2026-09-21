import type { NormalizationHistoryEntry } from "../types";

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "Chưa có thời gian";
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

export function HistoryList({
  entries,
  emptyMessage,
  title = "Lịch sử gần đây",
  deletingEntryId = null,
  onDelete,
}: {
  entries: NormalizationHistoryEntry[];
  emptyMessage: string;
  title?: string;
  deletingEntryId?: string | null;
  onDelete?: (entry: NormalizationHistoryEntry) => void | Promise<void>;
}) {
  return (
    <section className="panel history-panel">
      <div className="panel__header">
        <div>
          <p className="panel__label">Lịch sử chuẩn hóa</p>
          <h2>{title}</h2>
        </div>
      </div>

      {entries.length ? (
        <div className="history-list" data-testid="history-list">
          {entries.map((entry) => (
            <article key={entry.id} className="history-item">
              <div className="history-item__top">
                <div className="history-item__meta">
                  <span>{formatTimestamp(entry.created_at)}</span>
                  <span>{entry.source_kind}</span>
                </div>
                {onDelete ? (
                  <button
                    className="history-item__delete"
                    type="button"
                    disabled={deletingEntryId === entry.id}
                    onClick={() => void onDelete(entry)}
                  >
                    {deletingEntryId === entry.id ? "Đang xóa..." : "Xóa"}
                  </button>
                ) : null}
              </div>
              <div className="history-item__block">
                <p className="history-item__label">Đầu vào</p>
                <p>{entry.input_text}</p>
              </div>
              <div className="history-item__block">
                <p className="history-item__label">Đầu ra</p>
                <p>{entry.output_text || "Chưa có dữ liệu đầu ra."}</p>
              </div>
              <div className="history-item__footer">
                <span>{entry.error_types.length ? entry.error_types.join(", ") : "Không ghi nhận lỗi"}</span>
                <span>{entry.latency_ms ? `${Math.round(entry.latency_ms)} ms` : "Độ trễ chưa rõ"}</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="page-state">{emptyMessage}</div>
      )}
    </section>
  );
}
