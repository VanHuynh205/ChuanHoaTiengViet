import { useEffect, useState } from "react";
import { api, type AIMeaning, type AIMeaningDetail } from "../lib/api";
import { clearResponseCache } from "../hooks/useLiveNormalize";

const labels: Record<string, string> = { candidate: "Ứng viên", conditional_shared: "Dùng có điều kiện",
  confirmed: "Đã xác nhận", needs_review: "Cần xem xét", revoked: "Đã thu hồi" };

export function AdminAIMeanings({ token }: { token: string | null }) {
  const [filters, setFilters] = useState({ status: "", domain: "", abbr: "", offset: 0 });
  const [rows, setRows] = useState<AIMeaning[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState<AIMeaningDetail | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!token) return;
    let active = true;
    setBusy(true); setSelected([]); setDetail(null);
    api.aiMeanings(token, filters).then((items) => { if (active) { setRows(items); setError(""); } })
      .catch(() => { if (active) { setRows([]); setError("Không tải được ứng viên AI."); } })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [token, filters, refresh]);
  async function moderate(action: "revoke" | "confirm") {
    if (!token) return;
    setBusy(true); setError("");
    try {
      const result = await api.moderateAIMeanings(token, selected, action, reason.trim());
      clearResponseCache();
      setSelected([]); setDetail(null); setRefresh((n) => n + 1);
      if (result.cacheStatus !== "invalidated") setError("Đã lưu quyết định; không gửi lại. Bộ nhớ đệm chưa làm mới, nhưng nghĩa thu hồi đã bị chặn tái sử dụng.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không lưu được quyết định."); }
    finally { setBusy(false); }
  }
  async function view(id: string) {
    if (!token) return;
    setBusy(true); setDetail(null);
    try { setDetail(await api.aiMeaningDetail(token, id)); }
    catch { setError("Không tải được bằng chứng."); }
    finally { setBusy(false); }
  }
  return <section className="panel" aria-label="Kiểm duyệt nghĩa AI">
    <h2>Nghĩa AI và bằng chứng</h2>
    <p>Nghĩa dùng chung vẫn giới hạn theo ngữ cảnh. Xác nhận nghĩa xung đột cần thu hồi nghĩa cạnh tranh trước.</p>
    <label>Trạng thái <select value={filters.status} disabled={busy} onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}>
      <option value="">Tất cả</option>{Object.entries(labels).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
    </select></label>
    <label>Domain <input value={filters.domain} maxLength={100} onChange={(e) => setFilters({ ...filters, domain: e.target.value, offset: 0 })} /></label>
    <label>Viết tắt <input value={filters.abbr} maxLength={100} onChange={(e) => setFilters({ ...filters, abbr: e.target.value, offset: 0 })} /></label>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Đang xử lý…</p>}
    <table><thead><tr><th>Chọn</th><th>Viết tắt → nghĩa</th><th>Domain / trạng thái</th><th>Bằng chứng</th><th>Chi tiết</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.id}>
        <td><input type="checkbox" aria-label={`Chọn ${r.abbr}: ${r.meaning}`} disabled={busy} checked={selected.includes(r.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, r.id] : selected.filter((id) => id !== r.id))} /></td>
        <td>{r.abbr} → {r.meaning}</td><td>{r.domain} / {labels[r.status] ?? r.status}</td><td>{r.evidence_count}</td>
        <td><button disabled={busy} onClick={() => void view(r.id)}>Bằng chứng và audit</button></td>
      </tr>)}</tbody></table>
    {!busy && !rows.length && <p>Không có ứng viên phù hợp.</p>}
    <button disabled={busy || !filters.offset} onClick={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - 50) })}>Trang trước</button>
    <button disabled={busy || rows.length < 50} onClick={() => setFilters({ ...filters, offset: filters.offset + 50 })}>Trang sau</button>
    <label>Lý do quyết định <input maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
    <button disabled={busy || !selected.length || !reason.trim()} onClick={() => void moderate("revoke")}>Thu hồi mục đã chọn ({selected.length})</button>
    <button disabled={busy || !selected.length || !reason.trim()} onClick={() => void moderate("confirm")}>Xác nhận mục đã chọn</button>
    {detail && <aside aria-label="Bằng chứng và audit">
      <h3>{detail.candidate.abbr} → {detail.candidate.meaning}</h3>
      <p>{detail.candidate.provider} / {detail.candidate.model} · Confidence {detail.candidate.confidence} · Revision {detail.candidate.revision} · {detail.candidate.policy_version}</p>
      <h4>Ngữ cảnh đã che dữ liệu (tối đa 100 mục gần nhất)</h4>
      <ul>{detail.evidence.map((e, i) => <li key={i}><time>{e.created_at}</time> <code>{e.context_snippet}</code></li>)}</ul>
      <h4>Audit (tối đa 200 mục gần nhất)</h4>
      <ul>{detail.audit.map((a) => <li key={a.id}>{a.created_at} · {a.action} · {a.actor} · revision {a.revision} · {a.reason}</li>)}</ul>
    </aside>}
  </section>;
}
