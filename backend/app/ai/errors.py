"""Exception hierarchy for AI provider clients.

Naming uses the ``AI`` prefix to avoid shadowing Python builtins such as
``TimeoutError``. Callers are expected to import these names explicitly:

    from app.ai.errors import AIRateLimitError, AITimeoutError
"""

from __future__ import annotations


class AIError(Exception):
    """Base class for every AI provider failure mode."""


class AIAuthError(AIError):
    """Authentication failed (HTTP 401/403). Never retried."""


class AIRateLimitError(AIError):
    """Rate limit or AI budget exhausted (HTTP 429).

    Not retried automatically: callers surface it as ``semanticStatus`` /
    rule-based fallback so the per-user budget stays honest.
    """


class AITimeoutError(AIError):
    """Request did not complete before the configured timeout."""


class AIParseError(AIError):
    """Provider returned a payload we could not interpret as a response."""


class AINetworkError(AIError):
    """Generic transient network failure (5xx, connection error)."""


class AINetworkDisabledError(AIError):
    """AI is intentionally offline, unavailable, or missing provider credentials."""
