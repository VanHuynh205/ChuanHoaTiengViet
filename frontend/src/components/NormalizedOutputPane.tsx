import { useEffect, useRef, useState } from "react";

import type { LiveNormalizeResponse } from "../types";
import { KIND_LABELS, changeKindStyle, renderChangeSide } from "./ChangeComparison";
import { Icon } from "./Icon";
import { PendingNotice } from "./PendingNotice";

type CopyState = "idle" | "copying" | "copied" | "error";
type SemanticStatus = NonNullable<LiveNormalizeResponse["semanticStatus"]>;

const SEMANTIC_STATUS_LABELS: Record<SemanticStatus, string> = {
  not_needed: "Không cần kiểm tra",
  not_checked: "Chưa kiểm tra",
  verified: "Đã kiểm tra",
  uncertain: "Chưa đủ tin cậy",
  partial: "Đã kiểm tra một phần",
  unavailable: "Chưa sẵn sàng",
  quota: "Tạm dừng do giới hạn",
  error: "Kiểm tra lỗi",
};

const SEMANTIC_REASON_LABELS: Record<string, string> = {
  provider_checked: "đã nhận kết quả kiểm tra",
  fallback_model: "đã dùng model dự phòng vì model chính không hoàn thành",
  cache_hit: "dùng kết quả kiểm tra còn hiệu lực",
  waiting_for_ai: "đang chờ AI",
  unresolved_meaning: "còn nghĩa chưa rõ",
  no_semantic_signal: "không có tín hiệu cần kiểm tra",
  no_candidates: "không có phần cần kiểm tra",
  no_eligible_chunks: "không có phần đủ điều kiện",
  deferred_until_context: "chờ đủ ngữ cảnh",
  provider_unavailable: "nhà cung cấp chưa sẵn sàng",
  rate_limited: "đã chạm giới hạn",
    low_confidence: "độ tin cậy chưa đủ",
    dictionary_changed: "từ điển vừa thay đổi; cần cập nhật lại kết quả",
    ai_inferred_meaning: "đã chuẩn hóa theo nghĩa AI suy đoán phù hợp nhất; có thể chưa đúng ý người viết",
  chunk_scope_incomplete: "phạm vi chưa bao phủ toàn văn",
  timeout: "quá thời gian",
  provider_error: "nhà cung cấp gặp lỗi",
  no_provider_result: "chưa nhận được kết quả",
  dataset_only: "đang dùng dataset-only",
  conditional_shared_meaning: "dùng lại nghĩa AI có bằng chứng trong cùng ngữ cảnh",
  punctuation_policy: "giữ nguyên vì AI đề xuất thay dấu câu ngoài quy tắc",
};

function semanticStatusPresentation(data: LiveNormalizeResponse) {
  const status = data.semanticStatus ?? "not_needed";
  const verified = data.semanticVerifiedChunks ?? 0;
  const total = data.semanticTotalChunks ?? 0;
  const scope = total > 0 && status !== "not_needed" ? ` (${verified}/${total} phần)` : "";
  const reason = data.semanticStatusReason
    ? ` · ${SEMANTIC_REASON_LABELS[data.semanticStatusReason] ?? data.semanticStatusReason}`
    : "";
  const tone = ["unavailable", "quota", "error"].includes(status)
    ? "status-pill--error"
    : status === "verified" || status === "not_needed"
      ? "status-pill--ok"
      : "status-pill--syncing";
  return {
    label: `AI: ${SEMANTIC_STATUS_LABELS[status]}${scope}${reason}`,
    tone,
  };
}

async function copyTextToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();

  try {
    if (!document.execCommand("copy")) {
      throw new Error("Clipboard fallback failed");
    }
  } finally {
    textarea.remove();
  }
}

export function NormalizedOutputPane({
  data: currentData,
  originalText,
  isLoading,
  isSyncing,
  error,
}: {
  data: LiveNormalizeResponse | null;
  originalText?: string;
  isLoading: boolean;
  isSyncing: boolean;
  error: string | null;
}) {
  // Presentation only: keep the previous reading surface mounted while the
  // existing normalizer requests a fresh response. Never use it for history.
  const lastResult = useRef<LiveNormalizeResponse | null>(null);
  useEffect(() => {
    if (currentData) lastResult.current = currentData;
    else if (!originalText?.trim()) lastResult.current = null;
  }, [currentData, originalText]);
  const data = currentData ?? (originalText?.trim() && (isLoading || error) ? lastResult.current : null);
  const isPreviousResult = Boolean(data && !currentData);
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const copyResetTimerRef = useRef<number | null>(null);
  const outputText = data?.primaryOutput ?? "";
  const canCopyOutput = outputText.trim().length > 0 && !isPreviousResult;

  useEffect(() => {
    setCopyState("idle");
  }, [outputText]);

  useEffect(() => {
    if (copyState !== "copied" && copyState !== "error") {
      return undefined;
    }

    if (copyResetTimerRef.current !== null) {
      window.clearTimeout(copyResetTimerRef.current);
    }

    copyResetTimerRef.current = window.setTimeout(() => {
      setCopyState("idle");
      copyResetTimerRef.current = null;
    }, 1800);

    return () => {
      if (copyResetTimerRef.current !== null) {
        window.clearTimeout(copyResetTimerRef.current);
        copyResetTimerRef.current = null;
      }
    };
  }, [copyState]);

  async function handleCopyOutput() {
    if (!canCopyOutput || copyState === "copying") {
      return;
    }

    setCopyState("copying");
    try {
      await copyTextToClipboard(outputText);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }

  const copyButtonLabel =
    copyState === "copying"
      ? "Đang sao chép"
      : copyState === "copied"
        ? "Đã sao chép"
        : copyState === "error"
          ? "Thử lại"
          : "Sao chép";


  return (
    <section className="panel output-panel" data-testid="normalized-output-panel">
      <div className="panel__header">
        <h2><Icon name="spark" /> Kết quả chuẩn hóa</h2>
        <div className="output-panel__header-actions">
          {data ? (
            <button
              type="button"
              className="output-copy-button"
              data-copy-state={copyState}
              onClick={handleCopyOutput}
              disabled={!canCopyOutput || copyState === "copying"}
              aria-label="Sao chép kết quả chuẩn hóa"
              title="Sao chép kết quả chuẩn hóa"
            >
              <Icon name="copy" /><span>{copyButtonLabel}</span>
            </button>
          ) : null}
          <span
            className={`status-pill ${error ? "status-pill--error" : isLoading || isSyncing ? "status-pill--syncing" : "status-pill--ok"}`}
            role="status"
            data-testid="normalize-status"
          >
            {error ? "Không kết nối" : isLoading ? "Đang xử lý" : isSyncing ? "Đang cập nhật" : data ? "Đã đồng bộ" : "Chờ văn bản"}
          </span>
        </div>
      </div>

      {error ? <p className="output-panel__error" role="alert">{error}</p> : null}
      {data ? (
        <>
          <div className="output-panel__primary" tabIndex={0} aria-label="Nội dung kết quả chuẩn hóa" data-testid="primary-output">
            {renderChangeSide(data.primaryOutput, data.changes ?? [], "output")}
          </div>
          <div className="output-panel__meta">
            {isPreviousResult ? <span>Kết quả trước đó — chưa cập nhật theo văn bản hiện tại.</span> : null}
            <span>{Array.from(outputText).length.toLocaleString("vi-VN")} ký tự</span>
            <span>Lỗi đã sửa: {data.errorTypes.join(", ") || "không"}</span>
            <span>Độ trễ: {data.latencyMs} ms</span>
          </div>
          {data.changes?.length ? <div className="change-comparison__legend" aria-label="Chú giải loại thay đổi">
            {[...new Set(data.changes.flatMap((change) => change.kinds))].map((kind) => (
              <span key={kind}>
                <i
                  className={`change-swatch change-swatch--${kind}`}
                  style={changeKindStyle(kind)}
                  aria-hidden="true"
                />
                <span>{KIND_LABELS[kind] ?? kind}</span>
              </span>
            ))}
          </div> : null}

          {data ? (() => {
            const semantic = semanticStatusPresentation(data);
            return (
              <span
                className={`status-pill ${semantic.tone}`}
                data-testid="semantic-status"
                title="Phạm vi kiểm tra AI của kết quả hiện tại"
              >
                {semantic.label}
              </span>
            );
          })() : null}

          {data.phraseMatches && data.phraseMatches.length > 0 ? (
            <details className="output-panel__phrases" data-testid="phrase-matches">
              <summary>
                <span>Cụm từ đã ghép</span>
                <span>{data.phraseMatches.length}</span>
              </summary>
              <dl className="output-panel__phrase-list">
                {data.phraseMatches.map((match) => (
                  <div
                    className="phrase-match"
                    key={`${match.start}-${match.end}-${match.matched}`}
                    data-testid="phrase-match"
                    title={`source: ${match.source} · confidence: ${match.confidence.toFixed(2)}`}
                  >
                    <dt className="phrase-match__from">{match.matched}</dt>
                    <dd>
                      <span className="phrase-match__arrow"> → </span>
                      <span className="phrase-match__to">{match.expanded}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </details>
          ) : null}

          {data.ambiguities.some((ambiguity) => ambiguity.selected === ambiguity.abbr) ? (
            <div className="notice notice--pending" data-testid="uncertainty-notice">
              Chưa đủ căn cứ để chọn nghĩa cho: {data.ambiguities
                .filter((ambiguity) => ambiguity.selected === ambiguity.abbr)
                .map((ambiguity) => ambiguity.abbr)
                .join(", ")}. Phần này được giữ nguyên.
            </div>
          ) : null}

          {!isPreviousResult ? <PendingNotice submissions={data.pendingSubmissions} /> : null}
        </>
      ) : (
        <div className="output-empty" aria-busy={isLoading}>
          <img src="/images/vietnamese-ribbon.png" alt="" width="72" height="108" />
          <h3>{isLoading ? "Đang làm rõ từng chữ…" : "Lời rõ, ý trọn."}</h3>
          <p>{isLoading ? "Kết quả sẽ xuất hiện tại đây khi xử lý hoàn tất." : "Nhập văn bản ở khung nguồn để hệ thống hiển thị kết quả ngay."}</p>
        </div>
      )}
    </section>
  );
}
