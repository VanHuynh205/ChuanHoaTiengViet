import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { BrandMark } from "../components/BrandMark";
import { Icon } from "../components/Icon";
import { HighlightedSourceEditor } from "../components/HighlightedSourceEditor";
import { NormalizedOutputPane } from "../components/NormalizedOutputPane";
import { useLiveNormalize } from "../hooks/useLiveNormalize";
import { useDictionaryRevision } from "../hooks/useDictionaryRevision";
import { api } from "../lib/api";
import {
  clearWorkspaceDraft,
  readWorkspaceDraft,
  readWorkspaceLastSavedSignature,
  WORKSPACE_FLUSH_EVENT,
  writeWorkspaceDraft,
  writeWorkspaceLastSavedSignature,
} from "../lib/workspaceSession";
import type { LiveInputMethod, LiveNormalizeResponse } from "../types";

type HistorySnapshot = {
  inputText: string;
  outputText: string | null;
  errorTypes: string[];
  latencyMs: number | null;
  sourceKind: string;
  signature: string;
};

function buildHistorySnapshot(text: string, data: LiveNormalizeResponse | null): HistorySnapshot | null {
  const trimmedInput = text.trim();
  if (!trimmedInput) {
    return null;
  }

  const matched = data?.inputText === undefined || data.inputText === text;
  if (!matched) data = null;
  const outputText = data?.primaryOutput || null;
  const errorTypes = data?.errorTypes ?? [];
  const latencyMs = data?.latencyMs ?? null;
  const partial = !outputText || data?.normalizationPhase === "ai_pending" ||
    (data?.semanticStatus !== undefined && !["verified", "not_needed"].includes(data.semanticStatus));
  const sourceKind = partial ? "web_live_partial" : "web_live";
  return {
    inputText: text,
    outputText,
    errorTypes,
    latencyMs,
    sourceKind,
    signature: JSON.stringify({
      input: text,
      output: outputText ?? null,
      errorTypes,
      sourceKind,
      semanticStatus: data?.semanticStatus,
    }),
  };
}

export function WorkspacePage() {
  const { token, user } = useAuth();
  const [text, setText] = useState("");
  const [inputMethod, setInputMethod] = useState<LiveInputMethod>("typing");
  const [allowAi, setAllowAi] = useState(false);
  const dictionaryVersion = useDictionaryRevision(token);
  const lastRecordedSignature = useRef<string | null>(null);
  const flushInFlight = useRef<Promise<void> | null>(null);
  const ignoredSignatures = useRef<Set<string>>(new Set());
  const latestText = useRef("");
  const latestData = useRef<LiveNormalizeResponse | null>(null);
  const previousText = useRef("");
  const hydratedForUserId = useRef<string | null>(null);

  const { data, isLoading, isSyncing, error } = useLiveNormalize({
    text,
    token,
    resolutionOverrides: {},
    inputMethod,
    allowAi,
    dictionaryVersion,
  });

  latestText.current = text;

  useEffect(() => {
    latestData.current = data;
  }, [data]);

  useEffect(() => {
    if (previousText.current !== text) {
      // A response for the previous version may still be visible while the
      // typing debounce is pending. It must not be eligible for history flush.
      latestData.current = null;
      previousText.current = text;
    }
  }, [text]);

  useEffect(() => {
    if (!user?.id) {
      hydratedForUserId.current = null;
      return;
    }
    if (hydratedForUserId.current === user.id) {
      return;
    }

    hydratedForUserId.current = user.id;
    const draft = readWorkspaceDraft(user.id);
    setText(draft?.text ?? "");
    lastRecordedSignature.current = readWorkspaceLastSavedSignature(user.id);
  }, [user?.id]);

  useEffect(() => {
    if (!user?.id) {
      return;
    }
    if (!text) {
      clearWorkspaceDraft(user.id);
      return;
    }
    writeWorkspaceDraft(user.id, {
      text,
      resolutionOverrides: {},
    });
  }, [text, user?.id]);

  const flushHistory = useCallback(
    (keepalive = false) => {
      if (!token || !user?.id) {
        return Promise.resolve();
      }

      const snapshot = buildHistorySnapshot(latestText.current, latestData.current);
      if (!snapshot || snapshot.signature === lastRecordedSignature.current) {
        return Promise.resolve();
      }
      if (flushInFlight.current) {
        return flushInFlight.current;
      }

      const request = api
        .recordHistory(
          token,
          {
            inputText: snapshot.inputText,
            outputText: snapshot.outputText,
            errorTypes: snapshot.errorTypes,
            latencyMs: snapshot.latencyMs,
            sourceKind: snapshot.sourceKind,
          },
          { keepalive },
        )
        .then(() => {
          if (ignoredSignatures.current.has(snapshot.signature)) {
            ignoredSignatures.current.delete(snapshot.signature);
            lastRecordedSignature.current = null;
            writeWorkspaceLastSavedSignature(user.id, null);
            return;
          }
          lastRecordedSignature.current = snapshot.signature;
          writeWorkspaceLastSavedSignature(user.id, snapshot.signature);
        })
        .catch(() => undefined)
        .finally(() => {
          if (flushInFlight.current === request) {
            flushInFlight.current = null;
          }
        });

      flushInFlight.current = request;
      return request;
    },
    [token, user?.id],
  );

  useEffect(() => {
    const handleFinalize = () => {
      void flushHistory(false);
    };
    const handlePageHide = () => {
      void flushHistory(true);
    };

    window.addEventListener(WORKSPACE_FLUSH_EVENT, handleFinalize);
    window.addEventListener("pagehide", handlePageHide);

    return () => {
      window.removeEventListener(WORKSPACE_FLUSH_EVENT, handleFinalize);
      window.removeEventListener("pagehide", handlePageHide);
      void flushHistory(false);
    };
  }, [flushHistory]);

  function handleEditorChange(value: string, method: LiveInputMethod) {
    if (value !== latestText.current) {
      latestData.current = null;
    }
    if (!value && latestText.current) {
      const snapshot = buildHistorySnapshot(latestText.current, latestData.current);
      if (snapshot) {
        ignoredSignatures.current.add(snapshot.signature);
      }
      void flushHistory(false);
      // flushHistory returns early (leaving the entry above orphaned) whenever a
      // flush is already in flight or the snapshot was already recorded, so the
      // set has to be reset here rather than in a .then() that may never run.
      ignoredSignatures.current.clear();
      if (user?.id) {
        clearWorkspaceDraft(user.id);
        writeWorkspaceLastSavedSignature(user.id, null);
      }
      lastRecordedSignature.current = null;
    }

    setText(value);
    setInputMethod(method);
  }

  return (
    <section className="page-stack workspace-page">
      <header className="page-hero">
        <div className="page-hero__lead">
          <span className="page-hero__badge" aria-hidden="true"><BrandMark /></span>
          <div>
            <p className="workspace-kicker">Không gian làm việc</p>
            <h1>Không gian chuẩn hóa</h1>
            <p className="page-hero__copy">Nhập văn bản, nhận kết quả chuẩn hóa tiếng Việt nhanh chóng và chính xác.</p>
          </div>
        </div>
        <p className="workspace-script" aria-hidden="true">Tiếng Việt là một điều đẹp</p>
      </header>

      <aside className="workspace-ornament" aria-hidden="true">
        <p>viết đúng<br /><em>để hiểu nhau hơn</em></p>
        <img src="/images/vietnamese-ribbon.png" alt="" />
      </aside>

      {data?.diacriticApplied && data.diacriticChanges?.length ? (
        <div className="diacritic-result" data-testid="diacritic-inline">
          <span>
            Đã tự động khôi phục dấu ({data.diacriticChanges.length} từ thay đổi)
          </span>
        </div>
      ) : null}

      <div className="notice notice--info ai-consent" data-testid="ai-consent">
        <label>
          <input
            type="checkbox"
            checked={allowAi}
            onChange={(event) => setAllowAi(event.target.checked)}
          />
          Cho phép gửi văn bản hiện tại tới dịch vụ AI để kiểm tra toàn văn theo ngữ cảnh.
        </label>
        <details className="ai-consent__details"><summary>Thông tin về dữ liệu</summary><p>Dữ liệu phải phù hợp điều khoản nhà cung cấp; ứng dụng không cam kết lưu trữ bằng 0, không huấn luyện hoặc ẩn danh tuyệt đối.</p></details>
        <Icon name="info" />
      </div>

      <div className="workspace-grid">
        <HighlightedSourceEditor value={text} changes={data?.changes ?? []} onChange={handleEditorChange} />
        <NormalizedOutputPane
          data={data}
          originalText={text}
          isLoading={isLoading}
          isSyncing={isSyncing}
          error={error}
        />
      </div>
      <div className="workspace-footer">
        <p className="workspace-note">Kết quả tự động cập nhật khi bạn nhập. Phần tô màu thể hiện thay đổi thực tế; hãy kiểm tra lại để giữ đúng ý của bạn.</p>
        <span className="workspace-footer__hint"><Icon name="spark" /> Chuẩn hóa tự động</span>
      </div>
    </section>
  );
}
