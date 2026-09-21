import type { PendingSubmission } from "../types";

export function PendingNotice({ submissions }: { submissions: PendingSubmission[] }) {
  const abbreviations = [...new Set(
    submissions
      .map((submission) => submission.abbr.trim())
      .filter(Boolean),
  )];

  if (!abbreviations.length) {
    return null;
  }

  return (
    <div className="notice notice--pending" data-testid="pending-notice">
      <p>
        Đang chờ nghĩa được duyệt cho: <strong>{abbreviations.join(", ")}</strong>. Kết quả hiện tại vẫn giữ nguyên
        phần chưa đủ căn cứ.
      </p>
    </div>
  );
}
