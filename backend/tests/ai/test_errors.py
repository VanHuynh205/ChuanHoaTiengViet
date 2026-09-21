"""Tests for app.ai.errors hierarchy."""

from __future__ import annotations

import pytest

from app.ai.errors import (
    AIAuthError,
    AIError,
    AINetworkDisabledError,
    AINetworkError,
    AIParseError,
    AIRateLimitError,
    AITimeoutError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "subclass",
    [
        AIAuthError,
        AINetworkDisabledError,
        AINetworkError,
        AIParseError,
        AIRateLimitError,
        AITimeoutError,
    ],
)
def test_all_errors_inherit_from_aierror(subclass: type[AIError]) -> None:
    assert issubclass(subclass, AIError)
    assert issubclass(subclass, Exception)


@pytest.mark.unit
def test_aierror_carries_message() -> None:
    err = AIRateLimitError("hit 429")
    assert str(err) == "hit 429"
    assert isinstance(err, AIError)
