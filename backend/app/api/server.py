from __future__ import annotations

import logging
import re

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError:  # pragma: no cover - API layer is optional in this phase
    FastAPI = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    CORSMiddleware = None  # type: ignore[assignment]
    BaseHTTPMiddleware = None  # type: ignore[assignment]

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:  # pragma: no cover - dev environments without slowapi
    _rate_limit_exceeded_handler = None  # type: ignore[assignment]
    RateLimitExceeded = None  # type: ignore[assignment]
    SlowAPIMiddleware = None  # type: ignore[assignment]

from app.api.routes import limiter, router
from app.config import get_settings
from app.utils.logger import configure_logging

logger = logging.getLogger(__name__)

# Paths that must keep loading third-party assets (Swagger UI pulls JS/CSS from
# a CDN), so the strict CSP below cannot apply to them.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def _cors_origins(settings):
    """Allow the configured SPA origin and Vite's ephemeral dev ports."""
    configured = settings.web_origin.strip().rstrip("/")
    origins = [configured]
    if not settings.is_production and re.match(r"^https?://localhost(?::\d+)?$", configured):
        # Vite chooses 5174, 5175, ... when an earlier dev server is still up.
        origins.extend(["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"])
    return list(dict.fromkeys(origins))


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before anything buffers them in RAM.

    Written as a raw ASGI middleware rather than ``BaseHTTPMiddleware`` so the
    check happens while the body is still streaming: a client that lies in
    ``Content-Length`` is still cut off once the accumulated byte count crosses
    the limit.
    """

    def __init__(self, app, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or self.max_body_bytes <= 0:
            await self.app(scope, receive, send)
            return

        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() != b"content-length":
                continue
            try:
                declared = int(raw_value)
            except (TypeError, ValueError):
                break
            if declared > self.max_body_bytes:
                await self._reject(send)
                return
            break

        state = {"received": 0, "too_large": False, "responded": False}

        async def limited_receive():
            message = await receive()
            if message["type"] == "http.request":
                state["received"] += len(message.get("body", b""))
                if state["received"] > self.max_body_bytes:
                    state["too_large"] = True
                    # Starve the app of further body so it fails fast instead of
                    # continuing to accumulate bytes we already refused.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if state["too_large"]:
                if not state["responded"]:
                    state["responded"] = True
                    await self._reject(send)
                return
            state["responded"] = True
            await send(message)

        await self.app(scope, limited_receive, guarded_send)

    async def _reject(self, send) -> None:
        body = b'{"detail":"Noi dung gui len qua lon."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI chua duoc cai dat.")

    configure_logging()
    settings = get_settings()
    config_errors = settings.validate()
    if config_errors:
        for error in config_errors:
            logger.error("Configuration error: %s", error)
        # Refuse to start on ANY fatal config error, not just in production — an
        # unset APP_ENV must never silently disable the auth-secret checks.
        raise RuntimeError("Refusing to start: configuration is invalid. See logs for details.")

    app = FastAPI(
        title="He thong chuan hoa tieng Viet",
        # Interactive docs enumerate every admin endpoint; keep them off in prod.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    from app.data_manager.dictionary_state import DictionaryWriteCommittedError
    from starlette.responses import JSONResponse

    @app.exception_handler(DictionaryWriteCommittedError)
    async def dictionary_commit_error(request: Request, exc: DictionaryWriteCommittedError):
        return JSONResponse(status_code=503, content={
            "detail": "Đã lưu thay đổi vào SQL, nhưng chưa xác nhận được đồng bộ hoặc đọc lại. "
                      "Hãy kiểm tra mục đã lưu và thử đồng bộ JSON lại; không cần gửi lại thao tác lưu.",
            "database_committed": True,
        })
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if BaseHTTPMiddleware is not None:

        class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                response: Response = await call_next(request)
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                # The API only ever returns JSON, so a deny-everything CSP is
                # safe — except on the Swagger/ReDoc pages, which load assets
                # from a CDN and only exist outside production.
                if not request.url.path.startswith(_DOCS_PATHS):
                    response.headers["Content-Security-Policy"] = _STRICT_CSP
                if settings.is_production:
                    response.headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
                return response

        app.add_middleware(_SecurityHeadersMiddleware)

    if limiter is not None:
        app.state.limiter = limiter
        if SlowAPIMiddleware is not None:
            app.add_middleware(SlowAPIMiddleware)
        if RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
            app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Added last so it becomes the OUTERMOST layer: in Starlette the most
    # recently added middleware runs first, and the size check must precede
    # every layer that could touch the body.
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
    )

    if router:
        app.include_router(router)
    from app.api.ai_meaning_routes import router as ai_meaning_router
    app.include_router(ai_meaning_router)
    return app


app = create_app() if FastAPI is not None else None
