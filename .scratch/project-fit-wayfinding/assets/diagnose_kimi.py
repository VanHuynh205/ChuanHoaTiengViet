"""Bounded diagnostic harness. Synthetic input; never print credentials/headers."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
import httpx
from app.ai.admission import BudgetedClient, ai_user_scope
from app.ai.client import AIRequest
from app.ai.kimi_client import KimiClient
from app.config import get_settings
from dataclasses import replace


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deadline", type=int, default=20)
    parser.add_argument("--transport", choices=["httpx", "requests"], default="httpx")
    parser.add_argument("--metadata", action="store_true")
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--invalid-key", action="store_true")
    parser.add_argument("--http2", action="store_true")
    parser.add_argument("--invalid-payload", action="store_true")
    parser.add_argument("--poll-seconds", type=int)
    parser.add_argument("--request-id")
    parser.add_argument("--text-content", action="store_true")
    parser.add_argument("--owner-sample", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.deadline <= 300:
        raise SystemExit("Deadline must be 1..300 seconds")
    settings = replace(get_settings(), ai_timeout_seconds=args.deadline, ai_max_retries=0)
    if args.invalid_key:
        settings = replace(settings, nvidia_api_key="invalid-diagnostic-key")
    if settings.nvidia_base_url != "https://integrate.api.nvidia.com/v1":
        raise SystemExit("Unexpected endpoint")
    started = time.monotonic()

    def mark(stage, **safe):
        print(json.dumps({"stage": stage, "seconds": round(time.monotonic()-started, 3), **safe}), flush=True)

    async def trace(name, info):
        mark(name)

    async def headers_received(response):
        mark("response.headers", status=response.status_code, content_type=response.headers.get("content-type"),
             nvcf_status=response.headers.get("nvcf-status"), request_id=response.headers.get("nvcf-reqid"))
        if response.status_code >= 400:
            raw_body = (await response.aread())[:4096].decode("utf-8", errors="replace")
            mark("response.error", detail=raw_body.replace(settings.nvidia_api_key, "<REDACTED>"))

    class TracedHTTP(httpx.AsyncClient):
        def stream(self, *a, **kw):
            kw["extensions"] = {"trace": trace}
            if args.poll_seconds is not None:
                kw["headers"] = {**kw.get("headers", {}), "NVCF-POLL-SECONDS": str(args.poll_seconds)}
            if args.no_stream:
                kw["headers"] = {**kw.get("headers", {}), "Accept": "application/json"}
            return super().stream(*a, **kw)

    request = AIRequest(prompt='Return only this JSON: {"ok":true}', max_tokens=256, temperature=1)
    if args.owner_sample:
        request = AIRequest(prompt="bạn có thể nói tiếng Việt và có thể hiểu các từ viết tắt ( teencode ) không ?",
                            max_tokens=16384, temperature=1)
    async with TracedHTTP(http2=args.http2, timeout=httpx.Timeout(args.deadline, connect=5), event_hooks={"response": [headers_received]}) as http:
        if args.request_id:
            from uuid import UUID
            request_id = str(UUID(args.request_id))
            response = await http.get(settings.nvidia_base_url + "/status/" + request_id,
                                      headers={"Authorization": "Bearer " + settings.nvidia_api_key})
            mark("request.status", status=response.status_code)
            return 0 if response.status_code == 200 else 1
        if args.metadata:
            try:
                response = await http.get(settings.nvidia_base_url + "/models",
                                          headers={"Authorization": "Bearer " + settings.nvidia_api_key})
                payload = response.json()
                models = [item.get("id") for item in payload.get("data", [])] if isinstance(payload, dict) else []
                mark("models", status=response.status_code,
                     target_present=settings.nvidia_model in models,
                     model_count=len(models))
                return 0 if response.status_code == 200 else 1
            except Exception as exc:
                mark("metadata_failed", error_type=type(exc).__name__)
                return 1
        raw = KimiClient(settings.nvidia_api_key, reasoning_effort="low", client=http,
                         max_output_tokens=16384 if args.owner_sample else 8192,
                         reasoning_token_reserve=0 if args.owner_sample else 2048)
        if args.text_content or args.owner_sample:
            original_build_body = raw._build_body
            def text_body(request):
                body = original_build_body(request)
                body["messages"][-1]["content"] = request.prompt
                return body
            raw._build_body = text_body
        if args.invalid_payload:
            raw._build_body = lambda request: {}
        if args.no_stream:
            build_body = raw._build_body
            raw._build_body = lambda request: {**build_body(request), "stream": False}
        if args.transport == "requests":
            import requests
            body = raw._build_body(request)

            class RequestsProbe:
                def is_available(self):
                    return True

                async def complete(self, request):
                    def run():
                        mark("requests.send")
                        with requests.post(settings.nvidia_base_url + "/chat/completions",
                                           headers={"Authorization": "Bearer " + settings.nvidia_api_key,
                                                    "Accept": "text/event-stream"},
                                           json=body, stream=True,
                                           timeout=(5, args.deadline)) as response:
                            mark("requests.headers", status=response.status_code)
                            total = 0
                            for line in response.iter_lines(chunk_size=1):
                                if line:
                                    total += 1
                                    if total == 1:
                                        mark("requests.first_line")
                                    if line == b"data: [DONE]":
                                        mark("requests.done", lines=total)
                                        return True
                            return False
                    return await asyncio.to_thread(run)
            raw = RequestsProbe()
        try:
            with ai_user_scope("internal-kimi-diagnostic"):
                result = await BudgetedClient(raw, settings, "nvidia:"+settings.nvidia_api_key).complete(request)
            mark("complete", final_text=getattr(result, "text", None), stream_complete=bool(result))
        except Exception as exc:
            mark("failed", error_type=type(exc).__name__)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
