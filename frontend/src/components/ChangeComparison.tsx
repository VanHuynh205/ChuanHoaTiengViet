import type { CSSProperties } from "react";
import type { NormalizationChange } from "../types";

export const KIND_LABELS: Record<string, string> = {
  teencode: "Teencode/viết tắt",
  diacritic: "Dấu/chính tả",
  case: "Viết hoa",
  deletion: "Phần bị xóa",
  whitespace: "Khoảng trắng",
  punctuation: "Dấu câu",
  spelling: "Chính tả",
  ai: "AI theo ngữ cảnh",
};

export const KIND_COLORS: Record<string, string> = {
  teencode: "rgba(14, 116, 144, 0.2)",
  diacritic: "rgba(180, 83, 9, 0.2)",
  case: "rgba(124, 58, 237, 0.18)",
  deletion: "rgba(153, 27, 27, 0.18)",
  whitespace: "rgba(15, 118, 110, 0.18)",
  spelling: "rgba(71, 85, 105, 0.2)",
  punctuation: "#fce5bc",
  ai: "rgba(15, 118, 110, 0.12)",
};

/** Keep legend swatches and single-kind highlights on the same color source. */
export function changeKindStyle(kind: string): CSSProperties | undefined {
  const color = KIND_COLORS[kind];
  return color ? { backgroundColor: color } : undefined;
}

export function changeHighlightStyle(kinds: string[]): CSSProperties | undefined {
  // Keep AI edits visually distinct; dataset repairs share one quiet tint so
  // long Vietnamese text does not become a wall of competing colors.
  const visibleKinds = kinds.filter((kind) => kind === "ai" || kind === "teencode");
  const colors = (visibleKinds.length ? visibleKinds : ["dataset"])
    .map((kind) => kind === "dataset" ? "rgba(15, 118, 110, 0.08)" : KIND_COLORS[kind])
    .filter(Boolean);
  if (colors.length === 1) return { backgroundColor: colors[0] };
  if (colors.length === 0) return undefined;
  const stop = 100 / colors.length;
  return {
    backgroundImage: `linear-gradient(90deg, ${colors.map((color, index) => `${color} ${index * stop}%, ${color} ${(index + 1) * stop}%`).join(", ")})`,
  };
}

function changeLabel(change: NormalizationChange) {
  const label = change.kinds.map((kind) => KIND_LABELS[kind] ?? kind).join(" + ");
  const reasons: Record<string, string> = {
    known_typo: "Lỗi gõ đã có trong bộ quy tắc",
    explicit_question_opening: "Mẫu hỏi rõ ràng ở đầu câu",
  };
  const source = change.source === "ai_conditional" ? "Nghĩa AI dùng có điều kiện"
    : change.source === "ai_inferred" ? "Nghĩa AI suy đoán" : null;
  return [label, source, change.reason ? (reasons[change.reason] ?? change.reason) : null,
    change.confidence != null ? `Độ tin cậy ${Math.round(change.confidence * 100)}%` : null].filter(Boolean).join(" · ");
}

export function renderChangeSide(
  text: string,
  changes: NormalizationChange[],
  side: "original" | "output",
) {
  // Backend offsets are Unicode code points; JS string offsets are UTF-16.
  const characters = Array.from(text);
  const slice = (start: number, end?: number) => characters.slice(start, end).join("");
  const startKey = side === "original" ? "originalStart" : "outputStart";
  const endKey = side === "original" ? "originalEnd" : "outputEnd";
  const ranges = changes
    .map((change) => ({
      change,
      start: change[startKey],
      end: change[endKey],
    }))
    .filter(({ start, end, change }) => end >= start && start >= 0 && end <= characters.length &&
      (end > start || (side === "original" && change.outputEnd > change.outputStart)))
    .sort((left, right) => left.start - right.start);

  if (!ranges.length) {
    return text;
  }

  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const { change, start, end } of ranges) {
    if (start < cursor) {
      continue;
    }
    if (start > cursor) {
      parts.push(slice(cursor, start));
    }
    if (start === end) {
      parts.push(<span key={`${side}-${change.id}`} className="change-insertion-marker"
        role="img" aria-label={`Vị trí thêm ${change.outputText}: ${changeLabel(change)}`}
        title={changeLabel(change)} data-testid={`${side}-change-${change.id}`} />);
      cursor = start;
      continue;
    }
    parts.push(
      <mark
        className={`change-highlight ${change.kinds.map((kind) => `change-highlight--${kind}`).join(" ")}`}
        style={changeHighlightStyle(change.kinds)}
        key={`${side}-${change.id}`}
        title={changeLabel(change)}
        data-testid={`${side}-change-${change.id}`}
      >
        {slice(start, end)}
      </mark>,
    );
    cursor = end;
  }
  if (cursor < characters.length) {
    parts.push(slice(cursor));
  }
  return parts;
}

export function ChangeComparison({
  originalText,
  outputText,
  changes,
}: {
  originalText: string;
  outputText: string;
  changes: NormalizationChange[];
}) {
  if (!changes.length) {
    return null;
  }

  const kinds = [...new Set(changes.flatMap((change) => change.kinds))];
  return (
    <section className="change-comparison" data-testid="comparison-view" aria-label="Đối chiếu thay đổi">
      <div className="change-comparison__header">
        <div>
          <p className="panel__label">Đối chiếu thay đổi</p>
          <h3>Đối chiếu bản gốc và kết quả</h3>
        </div>
        <span>{changes.length} thay đổi</span>
      </div>

      <div className="change-comparison__legend" aria-label="Chú giải loại thay đổi">
        {kinds.map((kind) => (
          <span key={kind}>
            <i
              className={`change-swatch change-swatch--${kind}`}
              style={changeKindStyle(kind)}
              aria-hidden="true"
            />
            {KIND_LABELS[kind] ?? kind}
          </span>
        ))}
      </div>

      <div className="change-comparison__grid">
        <article className="change-comparison__pane" data-testid="comparison-original">
          <h4>Bản gốc</h4>
          <div className="change-comparison__text">{renderChangeSide(originalText, changes, "original")}</div>
        </article>
        <article className="change-comparison__pane" data-testid="comparison-output">
          <h4>Kết quả</h4>
          <div className="change-comparison__text">{renderChangeSide(outputText, changes, "output")}</div>
        </article>
      </div>

      <ul className="change-comparison__details" aria-label="Mô tả thay đổi">
        {changes.map((change) => (
          <li key={change.id}>
            <span>{changeLabel(change)}</span>
            <code>{change.originalText || "-"}</code>
            <span aria-hidden="true">→</span>
            <code>{change.outputText || "-"}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
