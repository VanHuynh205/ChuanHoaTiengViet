import { useRef } from "react";

import type { LiveInputMethod } from "../types";

export function LiveInputEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string, method: LiveInputMethod) => void;
}) {
  const wasPasted = useRef(false);

  return (
    <section className="panel editor-panel" data-testid="live-input-panel">
      <div className="panel__header">
        <div>
          <p className="panel__label">Văn bản nguồn</p>
          <h2>Nhập văn bản nguồn</h2>
        </div>
        <span className="panel__badge">Đang theo dõi</span>
      </div>
      <textarea
        className="editor-panel__textarea"
        data-testid="live-input-editor"
        placeholder="Ví dụ: Hôm nay b đã làm j r."
        value={value}
        onPaste={() => {
          wasPasted.current = true;
        }}
        onChange={(event) => {
          const method: LiveInputMethod = wasPasted.current ? "paste" : "typing";
          wasPasted.current = false;
          onChange(event.target.value, method);
        }}
      />
    </section>
  );
}
