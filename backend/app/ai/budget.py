"""Shared output-token budgeting for every AI call site.

``max_tokens=len(text) * 3`` grows without bound: a 50 000-character request
asked the provider for 150 000 completion tokens, which either gets rejected
outright or bills for an enormous response. Every call site now goes through
:func:`estimate_output_budget`, which scales with word count but is clamped.
"""

from __future__ import annotations

# Enough for a short structured reply even on tiny inputs.
MIN_OUTPUT_TOKENS = 256
# Fallback ceiling when no ``Settings`` is available (mirrors
# ``Settings.ai_max_output_tokens``).
DEFAULT_MAX_OUTPUT_TOKENS = 8192
# Roughly the number of tokens a Vietnamese word costs, with headroom for the
# JSON envelope the prompts ask for.
TOKENS_PER_WORD = 6


def estimate_output_budget(text: str, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> int:
    """Return a bounded ``max_tokens`` for a completion that rewrites *text*."""
    ceiling = max(MIN_OUTPUT_TOKENS, int(max_output_tokens))
    word_count = max(1, len(text.split()))
    return min(max(word_count * TOKENS_PER_WORD, MIN_OUTPUT_TOKENS), ceiling)
