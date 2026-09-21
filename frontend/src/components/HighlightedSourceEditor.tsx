import { Icon } from "./Icon";
import { useEffect, useRef, useState } from "react";
import type { LiveInputMethod, NormalizationChange } from "../types";
import { renderChangeSide } from "./ChangeComparison";

export function HighlightedSourceEditor({
  value,
  changes,
  onChange,
}: {
  value: string;
  changes: NormalizationChange[];
  onChange: (value: string, method: LiveInputMethod) => void;
}) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const copyTimerRef = useRef<number | undefined>(undefined);
  const wasPasted = useRef(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const syncScroll = () => {
    if (inputRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = inputRef.current.scrollTop;
      highlightRef.current.scrollLeft = inputRef.current.scrollLeft;
    }
  };

  // Reset the "copied" flag on a fixed timer; a new copy cancels the pending
  // reset so the label cannot flicker back early, and unmount cleans up.
  useEffect(() => () => window.clearTimeout(copyTimerRef.current), []);

  async function copySource() {
    if (!value.trim()) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopyState("copied");
      window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("error");
    }
  }

  return (
    <section className="panel editor-panel" data-testid="live-input-panel">
      <div className="panel__header">
        <h2 id="source-title"><Icon name="document" /> Văn bản nguồn</h2>
        <div className="editor-panel__actions">
          <span className="panel__badge">Tự động</span>
          <button className="editor-copy-button" type="button" onClick={copySource} disabled={!value.trim()} aria-label="Sao chép văn bản nguồn">
            <Icon name="copy" /> {copyState === "copied" ? "Đã sao chép" : copyState === "error" ? "Thử lại" : "Sao chép"}
          </button>
        </div>
      </div>
      <div className="highlighted-editor">
        <div ref={highlightRef} className="highlighted-editor__layer" aria-hidden="true">
          {renderChangeSide(value, changes, "original")}
        </div>
        <textarea
          aria-labelledby="source-title"
          ref={inputRef}
          className="editor-panel__textarea highlighted-editor__textarea"
          data-testid="live-input-editor"
          placeholder="Ví dụ: Hôm nay b đã làm j r."
          value={value}
          onPaste={() => { wasPasted.current = true; }}
          onScroll={syncScroll}
          onChange={(event) => {
            const method: LiveInputMethod = wasPasted.current ? "paste" : "typing";
            wasPasted.current = false;
            onChange(event.target.value, method);
          }}
        />
      </div>
      <div className="editor-footer"><span>Gõ hoặc dán văn bản của bạn</span><span>{Array.from(value).length.toLocaleString("vi-VN")} ký tự</span></div>
    </section>
  );
}
