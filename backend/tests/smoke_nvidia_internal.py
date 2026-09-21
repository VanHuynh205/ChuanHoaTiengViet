"""One authorized synthetic request, real NVIDIA model, in-memory repositories."""

import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_api import ApiTests
from app.ai.client import get_ai_usage_stats, reset_rate_limit_breaker
from app.ai.services import reset_ai_service_cache
from app.api.dependencies import get_current_user
import app.api.routes as routes


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--reasoning", choices=["low", "high", "max"])
    parser.add_argument("--model", help="Override model; defaults to server settings")
    parser.add_argument("--reasoning-budget", type=int)
    args = parser.parse_args()
    reset_rate_limit_breaker()
    reset_ai_service_cache()
    fixture = ApiTests()
    fixture.setUp()
    with tempfile.TemporaryDirectory(prefix="nvidia-smoke-") as directory:
        fixture.settings = replace(
            fixture.settings,
            data_dir=Path(directory),
            ai_provider="nvidia",
            nvidia_model=args.model or fixture.settings.nvidia_model,
            nvidia_reasoning_budget=(args.reasoning_budget if args.reasoning_budget is not None
                                     else fixture.settings.nvidia_reasoning_budget),
            nvidia_reasoning_effort=args.reasoning or fixture.settings.nvidia_reasoning_effort,
            ai_disable_network=False,
            ai_max_retries=0,
            ai_timeout_seconds=60,
            diacritic_auto_detect=False,
            semantic_verify_max_chunks=1,
            semantic_verify_max_concurrency=1,
        )
        if not fixture.settings.nvidia_api_key:
            raise SystemExit("NVIDIA_API_KEY is missing")
        if fixture.settings.nvidia_base_url != "https://integrate.api.nvidia.com/v1":
            raise SystemExit("Unexpected NVIDIA endpoint")
        del fixture.app.dependency_overrides[get_current_user]
        routes.UsageStatsRepository = lambda settings: SimpleNamespace(
            record_usage_bulk=lambda *a, **k: None
        )
        token = fixture._issue_token("user-1")
        started = time.monotonic()
        response = fixture.client.post(
            "/api/normalize/live",
            headers={"Authorization": "Bearer " + token},
            json={"text": "hôm nay dk học phần", "allowAI": True, "inputMethod": "paste"},
        )
        result = response.json()
        report = {
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "http_status": response.status_code,
            "model": fixture.settings.nvidia_model,
            "reasoning_effort": fixture.settings.nvidia_reasoning_effort,
            "semantic_status": result.get("semanticStatus"),
            "semantic_reason": result.get("semanticStatusReason"),
            "verified_chunks": result.get("semanticVerifiedChunks"),
            "output": result.get("primaryOutput"),
            "usage": get_ai_usage_stats(),
        }
        print(json.dumps(report, ensure_ascii=True))
        return (
            0 if response.status_code == 200 and result.get("semanticVerifiedChunks", 0) > 0 else 1
        )


if __name__ == "__main__":
    raise SystemExit(main())
