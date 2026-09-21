"""Host-local, cross-worker admission. No prompts or credentials are stored on disk."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from app.ai.errors import AINetworkError, AIRateLimitError, AITimeoutError
from app.config import PROJECT_ROOT

if TYPE_CHECKING:
    from app.ai.client import AIClient, AIRequest, AIResponse
    from app.config import Settings

_user: ContextVar[str] = ContextVar("ai_user", default="internal-cli")
# Nested clients (for example primary + fallback) must share one request deadline.
_deadline: ContextVar[float | None] = ContextVar("ai_deadline", default=None)


def user_cache_scope() -> str:
    return hashlib.sha256(_user.get().encode()).hexdigest()


@contextmanager
def ai_user_scope(user_id: object) -> Iterator[None]:
    token = _user.set(str(user_id))
    try:
        yield
    finally:
        _user.reset(token)


@contextmanager
def ai_deadline_scope(timeout_seconds: float) -> Iterator[None]:
    """Give a composed AI call one deadline shared by every child client."""
    if _deadline.get() is not None:
        yield
        return

    token = _deadline.set(asyncio.get_running_loop().time() + max(0.0, float(timeout_seconds)))
    try:
        yield
    finally:
        _deadline.reset(token)


def ai_deadline_remaining() -> float | None:
    """Return seconds left in the current composed AI call, if one exists."""
    deadline = _deadline.get()
    if deadline is None:
        return None
    return max(0.0, deadline - asyncio.get_running_loop().time())


class BudgetedClient:
    """Bound retries, concurrent calls and sliding-window attempts across local workers."""

    def __init__(self, client: AIClient, settings: Settings, account: str) -> None:
        self._client = client
        self._settings = settings
        self._account = hashlib.sha256(account.encode()).hexdigest()
        path = Path(settings.ai_budget_path).expanduser()
        self._path = path if path.is_absolute() else PROJECT_ROOT / path
        self._flights: WeakKeyDictionary = WeakKeyDictionary()

    @property
    def model(self) -> str:
        return str(getattr(self._client, "model", "unknown"))

    def is_available(self) -> bool:
        return self._client.is_available()

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._path, timeout=0.2)

    def _reserve(self, owner: str) -> str:
        now = time.time()
        s = self._settings
        lease = uuid.uuid4().hex
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, account TEXT, owner TEXT, started REAL, expires REAL)"
                )
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "DELETE FROM attempts WHERE account=? AND started <= ? AND expires <= ?",
                    (self._account, now - s.ai_budget_window_seconds, now),
                )
                total, own, active, own_active = db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(owner=?),0), COALESCE(SUM(expires>?),0), "
                    "COALESCE(SUM(owner=? AND expires>?),0) FROM attempts "
                    "WHERE account=? AND (started>? OR expires>?)",
                    (owner, now, owner, now, self._account, now - s.ai_budget_window_seconds, now),
                ).fetchone()
                if (
                    total >= s.ai_requests_per_window
                    or own >= s.ai_user_requests_per_window
                    or active >= s.ai_max_concurrency
                    or own_active >= s.ai_user_max_concurrency
                ):
                    raise AIRateLimitError("Application AI budget exhausted")
                db.execute(
                    "INSERT INTO attempts VALUES (?,?,?,?,?)",
                    (lease, self._account, owner, now, now + s.ai_timeout_seconds + 1),
                )
        except (OSError, sqlite3.Error) as exc:
            raise AIRateLimitError("Application AI budget unavailable") from exc
        return lease

    def _release(self, lease: str) -> None:
        # A failed release leaves a short lease that expires automatically.
        try:
            with closing(self._connect()) as db, db:
                db.execute("UPDATE attempts SET expires=0 WHERE id=?", (lease,))
        except (OSError, sqlite3.Error):
            logging.getLogger(__name__).warning("AI budget lease release failed; awaiting expiry")

    async def complete(self, request: AIRequest) -> AIResponse:
        import json

        owner = user_cache_scope()
        key = hashlib.sha256(
            (owner + json.dumps(asdict(request), sort_keys=True)).encode()
        ).hexdigest()
        flights = self._flights.setdefault(asyncio.get_running_loop(), {})
        if key in flights:
            return await asyncio.shield(flights[key])
        # The initiating task owns cancellation; identical waiters do not cancel it.
        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        flights[key] = future
        deadline_token = None
        deadline = _deadline.get()
        if deadline is None:
            deadline_token = _deadline.set(
                asyncio.get_running_loop().time() + self._settings.ai_timeout_seconds
            )
            deadline = _deadline.get()
        # ``set()`` above always seeds a value; assert narrows for mypy.
        assert deadline is not None  # nosec B101
        try:
            remaining = max(0.0, deadline - asyncio.get_running_loop().time())
            async with asyncio.timeout(remaining):
                for attempt in range(self._settings.ai_max_retries + 1):
                    lease = self._reserve(owner)
                    try:
                        response = await self._client.complete(request)
                        if not future.done():
                            # A waiter that hit its own deadline may already
                            # have set the exception; never overwrite it.
                            future.set_result(response)
                        return response
                    except AINetworkError:
                        if attempt == self._settings.ai_max_retries:
                            raise
                    finally:
                        self._release(lease)
                    await asyncio.sleep(min(0.25 * 2**attempt, 2))
            raise AITimeoutError("AI deadline exceeded")
        except TimeoutError as exc:
            error = AITimeoutError("AI deadline exceeded")
            if not future.done():
                future.set_exception(error)
            raise error from exc
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            if deadline_token is not None:
                _deadline.reset(deadline_token)
            flights.pop(key, None)
