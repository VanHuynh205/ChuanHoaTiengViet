import type { ReactNode } from "react";

import type { LiveVariant } from "../types";

function highlightMeanings(text: string, meanings: string[]): ReactNode[] {
  if (!meanings.length) {
    return [text];
  }

  const parts: ReactNode[] = [];
  let remaining = text;
  let keyIndex = 0;

  while (remaining.length > 0) {
    let earliestIndex = -1;
    let earliestMeaning = "";

    for (const meaning of meanings) {
      if (!meaning) continue;
      const idx = remaining.indexOf(meaning);
      if (idx !== -1 && (earliestIndex === -1 || idx < earliestIndex)) {
        earliestIndex = idx;
        earliestMeaning = meaning;
      }
    }

    if (earliestIndex === -1) {
      parts.push(remaining);
      break;
    }

    if (earliestIndex > 0) {
      parts.push(remaining.slice(0, earliestIndex));
    }
    parts.push(<mark key={keyIndex++}>{earliestMeaning}</mark>);
    remaining = remaining.slice(earliestIndex + earliestMeaning.length);
  }

  return parts;
}

export function AmbiguityHighlighter({
  variant,
}: {
  variant: LiveVariant;
}) {
  const meanings = variant.resolutions.map((r) => r.meaning).filter(Boolean);
  const highlighted = highlightMeanings(variant.output, meanings);

  return <p>{highlighted}</p>;
}
