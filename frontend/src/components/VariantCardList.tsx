import { useEffect, useMemo, useState } from "react";

import type { LiveVariant } from "../types";
import { AmbiguityHighlighter } from "./AmbiguityHighlighter";

export function VariantCardList({
  collapseAfterSelection = false,
  variants,
  selectedVariantId,
  onSelect,
}: {
  collapseAfterSelection?: boolean;
  variants: LiveVariant[];
  selectedVariantId: string | null;
  onSelect: (variant: LiveVariant) => void;
}) {
  const [showAll, setShowAll] = useState(true);

  useEffect(() => {
    if (!collapseAfterSelection || !selectedVariantId) {
      setShowAll(true);
    }
  }, [collapseAfterSelection, selectedVariantId, variants]);

  const visibleVariants = useMemo(() => {
    if (!collapseAfterSelection || showAll || !selectedVariantId) {
      return variants;
    }

    return variants.filter((variant) => variant.id === selectedVariantId);
  }, [collapseAfterSelection, selectedVariantId, showAll, variants]);

  if (variants.length <= 1) {
    return null;
  }

  return (
    <div className="variant-list" data-testid="variant-list">
      <div className="variant-list__header">
        <div>
          <p className="panel__label">Variant chooser</p>
          <h3>Chọn cách hiểu đúng cho cả câu</h3>
        </div>

        {collapseAfterSelection && selectedVariantId && !showAll ? (
          <button className="ghost-button" type="button" onClick={() => setShowAll(true)}>
            Xem lại toàn bộ phương án
          </button>
        ) : null}
      </div>

      <div className="variant-list__grid">
        {visibleVariants.map((variant) => {
          const isSelected = selectedVariantId === variant.id;

          return (
            <button
              key={variant.id}
              className={`variant-card ${isSelected ? "variant-card--selected" : ""}`}
              data-testid={`variant-card-${variant.id}`}
              onClick={() => {
                onSelect(variant);
                if (collapseAfterSelection) {
                  setShowAll(false);
                }
              }}
              type="button"
            >
              <div className="variant-card__meta">
                <span>{variant.isPrimary ? "Mặc định" : "Phương án thay thế"}</span>
                <span>{variant.resolutions.map((item) => item.meaning).join(" · ")}</span>
              </div>
              <AmbiguityHighlighter variant={variant} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
