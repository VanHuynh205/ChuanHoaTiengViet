import { useEffect, useMemo, useState } from "react";

import type { LiveAmbiguity } from "../types";

function sortNewestFirst(ambiguities: LiveAmbiguity[]) {
  return [...ambiguities].sort((left, right) => right.token_index - left.token_index);
}

export function AmbiguityChoiceList({
  ambiguities,
  selectedMeanings,
  onSelect,
}: {
  ambiguities: LiveAmbiguity[];
  selectedMeanings: Record<string, string>;
  onSelect: (ambiguityId: string, meaning: string) => void;
}) {
  const [isReviewMode, setIsReviewMode] = useState(false);
  const [editingAmbiguityId, setEditingAmbiguityId] = useState<string | null>(null);

  const newestFirstAmbiguities = useMemo(() => sortNewestFirst(ambiguities), [ambiguities]);
  const pendingAmbiguity = newestFirstAmbiguities.find((ambiguity) => !selectedMeanings[ambiguity.id]) ?? null;
  const editingAmbiguity = newestFirstAmbiguities.find((ambiguity) => ambiguity.id === editingAmbiguityId) ?? null;

  useEffect(() => {
    if (!editingAmbiguityId) {
      return;
    }

    if (!ambiguities.some((ambiguity) => ambiguity.id === editingAmbiguityId)) {
      setEditingAmbiguityId(null);
    }
  }, [ambiguities, editingAmbiguityId]);

  useEffect(() => {
    if (pendingAmbiguity) {
      setIsReviewMode(false);
      if (editingAmbiguityId && editingAmbiguityId !== pendingAmbiguity.id) {
        setEditingAmbiguityId(null);
      }
    }
  }, [editingAmbiguityId, pendingAmbiguity]);

  if (!ambiguities.length) {
    return null;
  }

  if (pendingAmbiguity) {
    const selectedMeaning = selectedMeanings[pendingAmbiguity.id] ?? pendingAmbiguity.selected;

    return (
      <div className="ambiguity-list" data-testid="ambiguity-list">
        <div className="variant-list__header">
          <div>
            <p className="panel__label">Word chooser</p>
            <h3>Chọn cách hiểu đúng</h3>
          </div>
        </div>

        <article className="ambiguity-card ambiguity-card--expanded" data-testid={`ambiguity-card-${pendingAmbiguity.id}`}>
          <div className="ambiguity-card__header">
            <div>
              <p className="panel__label">Từ đa nghĩa mới nhất</p>
              <h4>{pendingAmbiguity.abbr}</h4>
            </div>
          </div>

          <p className="ambiguity-card__summary">Gợi ý hiện tại: {selectedMeaning}</p>

          <div className="ambiguity-card__options">
            {pendingAmbiguity.options.map((option) => {
              const isSelected = option === selectedMeaning;

              return (
                <button
                  key={option}
                  aria-pressed={isSelected}
                  className={`ambiguity-option ${isSelected ? "ambiguity-option--selected" : ""}`}
                  type="button"
                  onClick={() => onSelect(pendingAmbiguity.id, option)}
                >
                  {option}
                </button>
              );
            })}
          </div>
        </article>
      </div>
    );
  }

  if (!isReviewMode) {
    return (
      <div className="ambiguity-list ambiguity-list--compact" data-testid="ambiguity-list">
        <div className="variant-list__header">
          <div>
            <p className="panel__label">Word chooser</p>
            <h3>Chọn cách hiểu đúng</h3>
          </div>
        </div>

        <div className="ambiguity-review-actions">
          <button className="ghost-button" type="button" onClick={() => setIsReviewMode(true)}>
            Chọn lại
          </button>
        </div>
      </div>
    );
  }

  if (!editingAmbiguity) {
    return (
      <div className="ambiguity-list" data-testid="ambiguity-list">
        <div className="variant-list__header">
          <div>
            <p className="panel__label">Word chooser</p>
            <h3>Chọn cách hiểu đúng</h3>
          </div>
        </div>

        <div className="ambiguity-review-actions">
          <button className="ghost-button" type="button" onClick={() => setIsReviewMode(false)}>
            Thoát
          </button>
        </div>

        <div className="ambiguity-list__stack">
          {newestFirstAmbiguities.map((ambiguity) => (
            <button
              key={ambiguity.id}
              className="ambiguity-card ambiguity-card--selectable"
              data-testid={`ambiguity-card-${ambiguity.id}`}
              type="button"
              onClick={() => setEditingAmbiguityId(ambiguity.id)}
            >
              <span className="ambiguity-card__abbr">{ambiguity.abbr}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const selectedMeaning = selectedMeanings[editingAmbiguity.id] ?? editingAmbiguity.selected;

  return (
    <div className="ambiguity-list" data-testid="ambiguity-list">
      <div className="variant-list__header">
        <div>
          <p className="panel__label">Word chooser</p>
          <h3>Chọn cách hiểu đúng</h3>
        </div>
      </div>

      <div className="ambiguity-review-actions">
        <button
          className="ghost-button"
          type="button"
          onClick={() => {
            setEditingAmbiguityId(null);
            setIsReviewMode(false);
          }}
        >
          Thoát
        </button>
      </div>

      <article className="ambiguity-card ambiguity-card--expanded" data-testid={`ambiguity-card-${editingAmbiguity.id}`}>
        <div className="ambiguity-card__header">
          <div>
            <p className="panel__label">Đổi lựa chọn</p>
            <h4>{editingAmbiguity.abbr}</h4>
          </div>
        </div>

        <div className="ambiguity-card__options">
          {editingAmbiguity.options.map((option) => {
            const isSelected = option === selectedMeaning;

            return (
              <button
                key={option}
                aria-pressed={isSelected}
                className={`ambiguity-option ${isSelected ? "ambiguity-option--selected" : ""}`}
                type="button"
                onClick={() => {
                  onSelect(editingAmbiguity.id, option);
                  setEditingAmbiguityId(null);
                }}
              >
                {option}
              </button>
            );
          })}
        </div>
      </article>
    </div>
  );
}
