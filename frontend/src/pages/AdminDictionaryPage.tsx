import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { api, ApiError } from "../lib/api";
import { clearResponseCache } from "../hooks/useLiveNormalize";
import type { ApprovedAbbreviation } from "../types";

function parseAlternativeExpansions(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildFormState(entry?: ApprovedAbbreviation | null) {
  return {
    abbr: entry?.abbr ?? "",
    expanded: entry?.expanded ?? "",
    domain: entry?.domain ?? "general",
    alternativeExpansionsText: entry?.alternative_expansions.join("\n") ?? "",
  };
}

function getEntryKey(entry: ApprovedAbbreviation) {
  return `${entry.domain}:${entry.abbr}`;
}

function sortDictionaryEntries(entries: ApprovedAbbreviation[]) {
  return [...entries].sort((left, right) => {
    const abbrComparison = left.abbr.localeCompare(right.abbr);
    return abbrComparison || left.domain.localeCompare(right.domain);
  });
}

export function AdminDictionaryPage() {
  const { token, user } = useAuth();
  const [entries, setEntries] = useState<ApprovedAbbreviation[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(buildFormState());
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [exportPending, setExportPending] = useState(false);
  const isAdmin = user?.roles.includes("admin") ?? false;
  useEffect(() => {
    let active = true;
    if (token && isAdmin) {
      void (async () => {
        try {
          const state = await api.dictionarySyncStatus(token);
          if (active) setExportPending(state.status === "export_failed");
        } catch { /* The save response also exposes synchronization failures. */ }
      })();
    }
    return () => { active = false; };
  }, [token, isAdmin]);

  const selectedEntry = useMemo(
    () => entries.find((entry) => getEntryKey(entry) === selectedKey) ?? null,
    [entries, selectedKey],
  );

  const filteredEntries = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return entries;
    }

    return entries.filter((entry) =>
      [entry.abbr, entry.expanded, ...entry.alternative_expansions]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery),
    );
  }, [entries, query]);

  useEffect(() => {
    if (!token) {
      return;
    }

    api
      .listAbbreviations(token)
      .then((response) => {
        setEntries(response);
        setError(null);
      })
      .catch((caughtError) => {
        setError(caughtError instanceof ApiError ? caughtError.message : "Không tải được dữ liệu từ điển.");
      });
  }, [token]);

  useEffect(() => {
    setForm(buildFormState(selectedEntry));
  }, [selectedEntry]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !isAdmin) {
      return;
    }
    const cleanedAbbr = form.abbr.trim();
    const cleanedExpanded = form.expanded.trim();
    if (!cleanedAbbr || !cleanedExpanded) {
      setStatusMessage(null);
      setError("Cần nhập cả từ viết tắt và nghĩa.");
      return;
    }

    try {
      setIsSaving(true);
      const saved = await api.saveAbbreviation(
        token,
        cleanedAbbr,
        cleanedExpanded,
        parseAlternativeExpansions(form.alternativeExpansionsText),
        form.domain,
      );
      setEntries((current) =>
        sortDictionaryEntries([
          ...current.filter((entry) => getEntryKey(entry) !== getEntryKey(saved)),
          saved,
        ]),
      );
      setSelectedKey(getEntryKey(saved));
      setForm(buildFormState(saved));
      setStatusMessage(`Đã lưu mục từ "${saved.abbr}".`);
      setExportPending(saved.dictionary_sync?.status === "export_failed");
      clearResponseCache();
      setError(null);
    } catch (caughtError) {
      setStatusMessage(null);
      if (caughtError instanceof ApiError && caughtError.databaseCommitted) setExportPending(true);
      setError(caughtError instanceof ApiError ? caughtError.message : "Không thể lưu mục từ điển lúc này.");
    } finally {
      setIsSaving(false);
    }
  }

  function handleResetForm() {
    setSelectedKey(null);
    setForm(buildFormState());
    setStatusMessage(null);
    setError(null);
  }

  async function handleDelete() {
    if (!token || !selectedEntry || !isAdmin || !window.confirm(`Xóa ${selectedEntry.abbr}?`)) return;
    try {
      await api.deleteAbbreviation(selectedEntry.abbr, token, selectedEntry.domain);
      setEntries((current) => current.filter((entry) => getEntryKey(entry) !== getEntryKey(selectedEntry)));
      handleResetForm();
      clearResponseCache();
      setStatusMessage(`Đã xóa mục từ "${selectedEntry.abbr}".`);
    } catch (caughtError) { setError(caughtError instanceof ApiError ? caughtError.message : "Không thể xóa mục từ điển."); }
  }

  return (
    <section className="page-stack">
      <header className="page-hero">
        <div>
          <p className="eyebrow">{isAdmin ? "Quản trị" : "Làm việc"}</p>
          <h1>Từ điển</h1>
          <p className="page-hero__copy">
            {isAdmin
              ? "Tra cứu toàn bộ từ viết tắt đã duyệt, thêm mục mới, cập nhật nghĩa gốc và quản lý các nghĩa bổ sung trên cùng một trang."
              : "Tra cứu từ viết tắt đã duyệt ở chế độ chỉ xem."}
          </p>
        </div>
      </header>

      {error ? <p className="form-error">{error}</p> : null}
      {statusMessage ? <div className="notice notice--info">{statusMessage}</div> : null}
      {exportPending && isAdmin ? <div className="notice notice--pending">
        Đã lưu vào SQL. Bản JSON chưa đồng bộ; dữ liệu SQL mới vẫn có hiệu lực khi SQL sẵn sàng.
        <button type="button" onClick={async () => {
          if (!token) return;
          try {
            const state = await api.retryDictionaryExport(token);
            setExportPending(state.status !== "synced");
            clearResponseCache();
          } catch { setError("Không thể đồng bộ JSON; thay đổi đã lưu trong SQL vẫn được giữ."); }
        }}>Thử đồng bộ JSON lại</button>
      </div> : null}

      <div className="dictionary-layout">
        <section className="panel dictionary-list-panel">
          <div className="panel__header">
            <div>
              <p className="panel__label">Từ điển</p>
              <h2>Danh sách từ viết tắt</h2>
            </div>
          </div>

          <label className="dictionary-search">
            <span className="panel__label">Tra cứu</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo từ viết tắt hoặc nghĩa" />
          </label>

          {filteredEntries.length ? (
            <div className="dictionary-list" data-testid="dictionary-list">
              {filteredEntries.map((entry) => (
                <button
                  key={getEntryKey(entry)}
                  className={`dictionary-list__item${getEntryKey(entry) === selectedKey ? " dictionary-list__item--selected" : ""}`}
                  type="button"
                  onClick={() => {
                    setSelectedKey(getEntryKey(entry));
                    setStatusMessage(null);
                  }}
                >
                  <div className="dictionary-list__content">
                    <strong>{entry.abbr}</strong>
                    <p>
                      <span className="dictionary-list__label">Nghĩa gốc:</span> {entry.expanded}
                    </p>
                    <p className="dictionary-list__alternatives">
                      <span className="dictionary-list__label">Nghĩa phụ:</span>{" "}
                      {entry.alternative_expansions.length ? entry.alternative_expansions.join(", ") : "Chưa có"}
                    </p>
                  </div>
                  <span className="dictionary-list__badge">{entry.domain}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="page-state">Không có mục từ nào khớp với truy vấn hiện tại.</div>
          )}
        </section>

        {isAdmin ? (
        <section className="panel dictionary-editor-panel">
          <div className="panel__header">
            <div>
                <p className="panel__label">Chỉnh sửa mục từ</p>
              <h2>{selectedEntry ? `Chỉnh sửa ${selectedEntry.abbr}` : "Thêm mục từ mới"}</h2>
            </div>
            <button className="ghost-button" type="button" onClick={handleResetForm}>
              Tạo mục mới
            </button>
            {selectedEntry ? <button className="ghost-button" type="button" onClick={handleDelete}>Xóa mục</button> : null}
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label>
              Từ viết tắt
              <input
                data-testid="dictionary-abbr-input"
                value={form.abbr}
                onChange={(event) => setForm((current) => ({ ...current, abbr: event.target.value }))}
                placeholder="Ví dụ: vch"
              />
            </label>
            <label>
              Nghĩa gốc
              <input
                data-testid="dictionary-expanded-input"
                value={form.expanded}
                onChange={(event) => setForm((current) => ({ ...current, expanded: event.target.value }))}
                placeholder="Ví dụ: văn chương học"
              />
            </label>
            <label>
              Nghĩa bổ sung
              <textarea
                data-testid="dictionary-alternatives-input"
                value={form.alternativeExpansionsText}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alternativeExpansionsText: event.target.value,
                  }))
                }
                placeholder={"Mỗi nghĩa một dòng\nVí dụ: văn chương hóa"}
                rows={7}
              />
            </label>

            <button data-testid="dictionary-submit" type="submit" disabled={isSaving}>
              {isSaving
                ? "Đang lưu..."
                : selectedEntry
                  ? "Lưu thay đổi"
                  : "Thêm vào từ điển"}
            </button>
          </form>

          {selectedEntry ? (
            <dl className="dictionary-meta">
              <div>
                <dt>Nguồn</dt>
                <dd>{selectedEntry.source}</dd>
              </div>
              <div>
                <dt>Duyệt bởi</dt>
                <dd>{selectedEntry.approved_by || "Chưa có"}</dd>
              </div>
              <div>
                <dt>Domain</dt>
                <dd>{selectedEntry.domain}</dd>
              </div>
            </dl>
          ) : null}
        </section>
        ) : (
          <section className="panel dictionary-editor-panel" data-testid="dictionary-readonly">
            <div className="panel__header">
              <div>
                <p className="panel__label">Chỉ xem</p>
                <h2>{selectedEntry ? selectedEntry.abbr : "Từ điển dùng chung"}</h2>
              </div>
            </div>
            <p className="notice notice--info">
              Tài khoản user chỉ được tra cứu và sử dụng nghĩa đã duyệt; không thể tạo nghĩa riêng.
            </p>
            {selectedEntry ? (
              <dl className="dictionary-meta">
                <div><dt>Nghĩa gốc</dt><dd>{selectedEntry.expanded}</dd></div>
                <div><dt>Nghĩa phụ</dt><dd>{selectedEntry.alternative_expansions.join(", ") || "Chưa có"}</dd></div>
                <div><dt>Domain</dt><dd>{selectedEntry.domain}</dd></div>
              </dl>
            ) : null}
          </section>
        )}
      </div>
    </section>
  );
}
