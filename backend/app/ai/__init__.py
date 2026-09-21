"""AI provider abstraction and concrete clients.

Public surface kept intentionally small so callers depend on the protocol
and the factory rather than concrete provider classes.
"""

from app.ai.cache import AsyncTTLCache, make_cache_key
from app.ai.client import (
    AIClient,
    AIRequest,
    AIResponse,
    NvidiaClient,
    NullClient,
    build_default_client,
    get_ai_usage_stats,
    reset_ai_usage_stats,
)
from app.ai.errors import (
    AIAuthError,
    AIError,
    AINetworkDisabledError,
    AINetworkError,
    AIParseError,
    AIRateLimitError,
    AITimeoutError,
)

__all__ = [
    "AIClient",
    "AIRequest",
    "AIResponse",
    "AIError",
    "AIAuthError",
    "AINetworkDisabledError",
    "AINetworkError",
    "AIParseError",
    "AIRateLimitError",
    "AITimeoutError",
    "AsyncTTLCache",
    "NvidiaClient",
    "NullClient",
    "build_default_client",
    "get_ai_usage_stats",
    "make_cache_key",
    "reset_ai_usage_stats",
]
