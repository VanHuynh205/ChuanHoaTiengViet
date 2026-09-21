import { useMemo } from "react";

import type { ExpandedAbbreviation } from "../types";

type HighlightSpan = {
  start: number;
  end: number;
  abbr: string;
  expanded: string;
};

function stripDiacritics(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function foldForMatch(text: string): string {
  return stripDiacritics(text).replace(/đ/g, "d");
}

// Decomposing the WHOLE string once is dramatically cheaper than calling
// String.prototype.normalize per character, which is what made typing lag on
// long texts. Combining marks map back to the base character's index.
function buildFoldedIndexMap(text: string): { foldedText: string; indexMap: number[] } {
  const foldedChars: string[] = [];
  const indexMap: number[] = [];

  const decomposed = text.normalize("NFD");
  let sourceIndex = -1;
  for (const char of decomposed) {
    const isCombiningMark = char >= "̀" && char <= "ͯ";
    if (!isCombiningMark) {
      sourceIndex += 1;
    }
    if (isCombiningMark) {
      continue;
    }
    const folded = (char === "đ" || char === "Đ" ? "d" : char).toLowerCase();
    foldedChars.push(folded);
    indexMap.push(sourceIndex);
  }

  return { foldedText: foldedChars.join(""), indexMap };
}

function isWordChar(char: string): boolean {
  return /[\p{L}\p{N}]/u.test(char);
}

function isSpanBoundary(text: string, start: number, end: number): boolean {
  return (
    (start <= 0 || !isWordChar(text[start - 1])) &&
    (end >= text.length || !isWordChar(text[end]))
  );
}

function allowsFoldedFallback(needle: string): boolean {
  const folded = foldForMatch(needle);
  return folded.includes(" ") || folded.length >= 4;
}

function buildHighlightSpans(
  text: string,
  expandedAbbreviations: ExpandedAbbreviation[],
): HighlightSpan[] {
  const spans: HighlightSpan[] = [];
  const { foldedText, indexMap } = buildFoldedIndexMap(text);
  const lowerText = text.toLowerCase();

  const usedRanges: [number, number][] = [];

  function overlaps(start: number, end: number): boolean {
    return usedRanges.some(([s, e]) => start < e && end > s);
  }

  function findFirstUnused(needle: string, abbr: string): HighlightSpan | null {
    const needleLower = needle.toLowerCase();
    let exactSearchFrom = 0;
    while (exactSearchFrom < lowerText.length) {
      const idx = lowerText.indexOf(needleLower, exactSearchFrom);
      if (idx === -1) break;
      const end = idx + needle.length;
      if (isSpanBoundary(text, idx, end) && !overlaps(idx, end)) {
        return { start: idx, end, abbr, expanded: text.slice(idx, end) };
      }
      exactSearchFrom = idx + 1;
    }

    if (!allowsFoldedFallback(needle)) {
      return null;
    }

    const needleFolded = foldForMatch(needle);
    if (!needleFolded) return null;

    let searchFrom = 0;
    while (searchFrom < foldedText.length) {
      const idx = foldedText.indexOf(needleFolded, searchFrom);
      if (idx === -1) return null;
      const foldedEnd = idx + needleFolded.length;
      const start = indexMap[idx];
      const end = indexMap[foldedEnd - 1] + 1;
      if (isSpanBoundary(text, start, end) && !overlaps(start, end)) {
        return { start, end, abbr, expanded: text.slice(start, end) };
      }
      searchFrom = idx + 1;
    }
    return null;
  }

  for (const ea of expandedAbbreviations) {
    const abbr = ea.abbr.trim();
    const expanded = ea.expanded.trim();
    if (!abbr || !expanded || stripDiacritics(abbr) === stripDiacritics(expanded)) continue;

    const hasBackendSpan =
      Number.isInteger(ea.start) &&
      Number.isInteger(ea.end) &&
      typeof ea.start === "number" &&
      typeof ea.end === "number" &&
      ea.start >= 0 &&
      ea.end > ea.start &&
      ea.end <= text.length &&
      foldForMatch(text.slice(ea.start, ea.end)) === foldForMatch(expanded);
    const span = hasBackendSpan
      ? { start: ea.start as number, end: ea.end as number, abbr, expanded }
      : findFirstUnused(expanded, abbr);
    if (span) {
      if (overlaps(span.start, span.end)) continue;
      usedRanges.push([span.start, span.end]);
      spans.push(span);
    }
  }

  spans.sort((a, b) => a.start - b.start);
  return spans;
}

export function HighlightedOutput({
  text,
  expandedAbbreviations,
}: {
  text: string;
  expandedAbbreviations: ExpandedAbbreviation[];
}) {
  // Recomputed on every render before — including every keystroke — even when
  // neither the text nor the spans had changed.
  const spans = useMemo(
    () => buildHighlightSpans(text, expandedAbbreviations),
    [text, expandedAbbreviations],
  );

  if (!spans.length) {
    return <p>{text}</p>;
  }

  const parts: React.ReactNode[] = [];
  let cursor = 0;

  for (const span of spans) {
    if (span.start > cursor) {
      parts.push(text.slice(cursor, span.start));
    }
    const highlighted = text.slice(span.start, span.end);
    parts.push(
      <span
        key={`${span.start}-${span.end}`}
        className="abbr-highlight"
        title={`Viết tắt: ${span.abbr}`}
      >
        {highlighted}
      </span>,
    );
    cursor = span.end;
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return <p>{parts}</p>;
}
