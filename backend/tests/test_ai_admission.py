import asyncio
from dataclasses import replace

import pytest

from app.ai.admission import BudgetedClient, ai_user_scope
from app.ai.client import AIRequest, AIResponse
from app.ai.errors import AIRateLimitError, AITimeoutError
from app.config import Settings


class FakeClient:
    model = "fake"

    def __init__(self, delay=0):
        self.calls = 0
        self.delay = delay

    def is_available(self):
        return True

    async def complete(self, request):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return AIResponse(request.prompt, 1, 0, self.model)


def settings_for(tmp_path, **kwargs):
    return replace(
        Settings(), ai_budget_path=str(tmp_path / "budget.sqlite3"), ai_max_retries=0, **kwargs
    )


@pytest.mark.asyncio
async def test_two_clients_share_budget_and_users_have_separate_caps(tmp_path):
    settings = settings_for(tmp_path, ai_user_requests_per_window=1, ai_requests_per_window=2)
    fake = FakeClient()
    first = BudgetedClient(fake, settings, "account")
    second = BudgetedClient(fake, settings, "account")
    with ai_user_scope("alice"):
        await first.complete(AIRequest("one"))
        with pytest.raises(AIRateLimitError):
            await second.complete(AIRequest("two"))
    with ai_user_scope("bob"):
        await second.complete(AIRequest("two"))
    with ai_user_scope("charlie"):
        with pytest.raises(AIRateLimitError):
            await first.complete(AIRequest("three"))
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_duplicate_calls_reuse_only_within_user(tmp_path):
    fake = FakeClient(0.01)
    client = BudgetedClient(fake, settings_for(tmp_path), "account")
    with ai_user_scope("alice"):
        responses = await asyncio.gather(*(client.complete(AIRequest("same")) for _ in range(4)))
    assert len(responses) == 4
    assert fake.calls == 1
    with ai_user_scope("bob"):
        await client.complete(AIRequest("same"))
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_different_dictionary_versions_do_not_share_inflight_reply(tmp_path):
    fake = FakeClient(0.01)
    client = BudgetedClient(fake, settings_for(tmp_path), "account")
    with ai_user_scope("alice"):
        await asyncio.gather(client.complete(AIRequest("same", cache_namespace="1")),
                             client.complete(AIRequest("same", cache_namespace="2")))
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_timeout_releases_shared_concurrency_lease(tmp_path):
    settings = settings_for(tmp_path, ai_timeout_seconds=0.02, ai_max_concurrency=1)
    client = BudgetedClient(FakeClient(1), settings, "account")
    with pytest.raises(AITimeoutError):
        await client.complete(AIRequest("slow"))
    fast = BudgetedClient(FakeClient(), settings, "account")
    assert (await fast.complete(AIRequest("fast"))).text == "fast"


@pytest.mark.asyncio
async def test_concurrent_clients_do_not_exceed_global_limit(tmp_path):
    settings = settings_for(tmp_path, ai_max_concurrency=1)
    fake = FakeClient(0.03)
    clients = [BudgetedClient(fake, settings, "account") for _ in range(2)]
    results = await asyncio.gather(
        *(c.complete(AIRequest(str(i))) for i, c in enumerate(clients)), return_exceptions=True
    )
    assert sum(isinstance(r, AIRateLimitError) for r in results) == 1
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_retry_attempts_each_consume_budget(tmp_path):
    from app.ai.errors import AINetworkError

    class FailingClient(FakeClient):
        async def complete(self, request):
            self.calls += 1
            raise AINetworkError("fake transient")

    settings = replace(settings_for(tmp_path, ai_user_requests_per_window=1), ai_max_retries=2)
    fake = FailingClient()
    with pytest.raises(AIRateLimitError):
        await BudgetedClient(fake, settings, "account").complete(AIRequest("retry"))
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_unwritable_ledger_fails_closed(tmp_path):
    settings = settings_for(tmp_path)
    settings = replace(settings, ai_budget_path=str(tmp_path))
    fake = FakeClient()
    with pytest.raises(AIRateLimitError):
        await BudgetedClient(fake, settings, "account").complete(AIRequest("blocked"))
    assert fake.calls == 0


def _complete_in_process(path):
    settings = replace(
        Settings(),
        ai_budget_path=path,
        ai_requests_per_window=1,
        ai_user_requests_per_window=1,
        ai_max_retries=0,
    )
    client = BudgetedClient(FakeClient(), settings, "same-account")
    try:
        asyncio.run(client.complete(AIRequest("cross-process")))
        return "admitted"
    except AIRateLimitError:
        return "denied"


@pytest.mark.asyncio
async def test_fallback_shares_one_total_deadline(tmp_path):
    from app.ai.errors import AITimeoutError
    from app.ai.fallback_client import FallbackClient

    settings = settings_for(tmp_path, ai_timeout_seconds=0.03)
    primary = BudgetedClient(FakeClient(1), settings, "primary")
    fallback = BudgetedClient(FakeClient(1), settings, "fallback")
    client = FallbackClient(primary, fallback)

    started = asyncio.get_running_loop().time()
    with pytest.raises(AITimeoutError, match="AI deadline exceeded"):
        await client.complete(AIRequest("slow fallback"))
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed < 0.08


@pytest.mark.asyncio
async def test_fallback_gets_time_after_primary_timeout(tmp_path):
    from app.ai.fallback_client import FallbackClient

    settings = settings_for(tmp_path, ai_timeout_seconds=0.1)
    primary = BudgetedClient(FakeClient(1), settings, "primary")
    secondary = BudgetedClient(FakeClient(0), settings, "fallback")
    result = await FallbackClient(primary, secondary).complete(AIRequest("fallback"))
    assert result.text == "fallback"
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_fallback_children_share_the_same_deadline(tmp_path):
    from app.ai.fallback_client import FallbackClient
    from app.ai.admission import _deadline
    from app.ai.errors import AINetworkError

    class FailingClient(FakeClient):
        async def complete(self, request):
            self.calls += 1
            self.deadline = _deadline.get()
            raise AINetworkError("primary unavailable")

    class ObservingClient(FakeClient):
        async def complete(self, request):
            self.calls += 1
            self.deadline = _deadline.get()
            return AIResponse("fallback", 1, 0, self.model)

    settings = settings_for(tmp_path, ai_timeout_seconds=0.2)
    primary = BudgetedClient(FailingClient(), settings, "primary")
    fallback = BudgetedClient(ObservingClient(), settings, "fallback")
    result = await FallbackClient(primary, fallback).complete(AIRequest("shared deadline"))

    assert result.text == "fallback"
    assert primary._client.deadline is not None
    assert fallback._client.deadline is not None
    assert abs(primary._client.deadline - fallback._client.deadline) < 0.02


def test_budget_survives_separate_worker_processes(tmp_path):
    from concurrent.futures import ProcessPoolExecutor

    path = str(tmp_path / "shared.sqlite3")
    with ProcessPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(_complete_in_process, [path, path]))
    assert sorted(results) == ["admitted", "denied"]
