import type { PendingAbbreviation } from "../types";

export function AdminPendingTable({
  pendingItems,
  onView,
  onApprove,
  onReject,
}: {
  pendingItems: PendingAbbreviation[];
  onView: (pending: PendingAbbreviation) => void;
  onApprove: (pending: PendingAbbreviation) => void;
  onReject: (pending: PendingAbbreviation) => void;
}) {
  return (
    <section className="panel admin-table" data-testid="pending-table">
      <div className="panel__header">
        <div>
          <p className="panel__label">Bảng kiểm duyệt</p>
          <h2>Danh sách pending</h2>
        </div>
      </div>
      <div className="admin-table__scroller">
        {pendingItems.length ? (
          <table>
            <thead>
              <tr>
                <th>Từ viết tắt</th>
                <th>Nghĩa đã nhập</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {pendingItems.map((item) => (
                <tr key={item.id} data-testid={`pending-row-${item.id}`}>
                  <td>{item.abbr}</td>
                  <td>{item.suggested_meanings.join(", ") || "Chưa có"}</td>
                  <td>{item.status}</td>
                  <td className="admin-table__actions">
                    <button data-testid={`view-pending-${item.id}`} type="button" onClick={() => onView(item)}>Xem</button>
                    <button data-testid={`approve-pending-${item.id}`} type="button" onClick={() => onApprove(item)}>Duyệt</button>
                    <button data-testid={`reject-pending-${item.id}`} type="button" onClick={() => onReject(item)}>Từ chối</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="page-state">Hiện chưa có pending nào cần kiểm duyệt.</div>
        )}
      </div>
    </section>
  );
}
