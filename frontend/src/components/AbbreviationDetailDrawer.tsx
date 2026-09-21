import type { ApprovedAbbreviation } from "../types";

export function AbbreviationDetailDrawer({
  detail,
  onClose,
}: {
  detail: ApprovedAbbreviation | null;
  onClose: () => void;
}) {
  if (!detail) {
    return null;
  }

  return (
    <aside className="drawer">
      <div className="drawer__header">
        <div>
          <p className="panel__label">Chi tiết viết tắt</p>
          <h3>{detail.abbr}</h3>
        </div>
        <button type="button" onClick={onClose}>
          Đóng
        </button>
      </div>
      <div className="drawer__content">
        <div>
          <span className="drawer__label">Nghĩa chính</span>
          <p>{detail.expanded}</p>
        </div>
        <div>
          <span className="drawer__label">Nghĩa phụ đã duyệt</span>
          <ul>
            {detail.alternative_expansions.length ? (
              detail.alternative_expansions.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li>Chưa có nghĩa phụ.</li>
            )}
          </ul>
        </div>
      </div>
    </aside>
  );
}
