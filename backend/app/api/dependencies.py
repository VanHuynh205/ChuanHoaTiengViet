from __future__ import annotations

from typing import Optional

from app.auth.security import decode_access_token
from app.config import Settings, get_settings
from app.data_manager.new_tables_repo import SessionRepository
from app.data_manager.user_repo import UserRepository

try:
    from fastapi import Depends, Header, HTTPException, Request
except ImportError:  # pragma: no cover - API layer is optional in this phase
    Depends = None  # type: ignore[assignment]
    Header = None  # type: ignore[assignment]
    HTTPException = RuntimeError  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]

BEARER_PREFIX = "Bearer "


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Return the raw token from an ``Authorization`` header, or ``None``.

    Shared by the auth dependency and the logout route so both hash exactly the
    same string — they used to differ by a ``.strip()``, which meant a header
    with trailing whitespace produced a revoke that never matched the stored
    session row.
    """
    if not authorization or not authorization.startswith(BEARER_PREFIX):
        return None
    token = authorization[len(BEARER_PREFIX) :].strip()
    return token or None


def get_app_settings() -> Settings:
    return get_settings()


def _get_user_repository(settings: Settings = Depends(get_app_settings)) -> UserRepository:
    return UserRepository(settings)


def _get_session_repository(settings: Settings = Depends(get_app_settings)) -> SessionRepository:
    return SessionRepository(settings)


def get_current_user(
    request: Request = None,  # type: ignore[assignment]
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_app_settings),
    repository: UserRepository = Depends(_get_user_repository),
    session_repository: SessionRepository = Depends(_get_session_repository),
):
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Ban chua dang nhap.")

    try:
        payload = decode_access_token(token, settings)
    except ValueError:
        # Do not echo the underlying validation message — keep the response generic.
        raise HTTPException(status_code=401, detail="Token khong hop le hoac da het han.")

    if not session_repository.is_token_valid(token):
        raise HTTPException(status_code=401, detail="Token khong hop le hoac da het han.")

    if not repository.is_ready():
        raise HTTPException(status_code=503, detail="SQL Server chua san sang")

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=401, detail="Token khong hop le hoac da het han.")

    user = repository.find_by_id(subject)
    if not user:
        raise HTTPException(status_code=401, detail="Khong tim thay tai khoan.")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Tai khoan da bi vo hieu hoa.")

    # Publish the resolved user so the slowapi key function can rate-limit per
    # account instead of per IP. Decorated routes run their limit check inside
    # the endpoint, i.e. after this dependency has completed.
    if request is not None:
        request.state.user = user
    return user


def require_role(role_name: str):
    def dependency(current_user=Depends(get_current_user)):
        if role_name not in current_user.get("roles", []):
            raise HTTPException(
                status_code=403, detail="Ban khong co quyen thuc hien thao tac nay."
            )
        return current_user

    return dependency


async def get_ai_user(current_user=Depends(get_current_user)):
    from app.ai.admission import ai_user_scope

    with ai_user_scope(current_user["id"]):
        yield current_user
