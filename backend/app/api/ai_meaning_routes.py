from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from app.api.dependencies import get_app_settings, require_role
from app.data_manager.ai_meaning_repo import AIMeaningRepository
from app.data_manager.pending_service import PendingAbbreviationService
from app.data_manager.dictionary_state import DictionaryState

router = APIRouter(prefix="/api/admin/ai-meanings", dependencies=[Depends(require_role("admin"))])


def repository(settings=Depends(get_app_settings)):
    return AIMeaningRepository(settings)


class ModerationRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=100)
    action: Literal["revoke", "confirm"]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonempty_reason(cls, value):
        if not value.strip():
            raise ValueError("A moderation reason is required")
        return value.strip()


@router.get("")
def list_meanings(
    status: (
        Literal["candidate", "conditional_shared", "confirmed", "needs_review", "revoked"] | None
    ) = None,
    domain: str | None = Query(None, max_length=100),
    abbr: str | None = Query(None, max_length=100),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    repo=Depends(repository),
):
    return repo.list(status, domain, abbr, offset, limit)


@router.get("/{candidate_id}")
def detail(candidate_id: UUID, repo=Depends(repository)):
    result = repo.detail(str(candidate_id))
    if result is None:
        raise HTTPException(404, "Candidate not found")
    return result


@router.post("/moderate")
def moderate(
    payload: ModerationRequest, repo=Depends(repository), admin=Depends(require_role("admin"))
):
    try:
        rows = repo.moderate(
            [str(id) for id in payload.ids],
            payload.action,
            str(admin["id"]),
            payload.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    PendingAbbreviationService.invalidate_live_normalization_cache()
    # Reuse reads SQL on every request. This revision additionally wakes clients
    # and invalidates dataset caches across local workers.
    try:
        DictionaryState(repo.settings.data_dir).bump()
    except Exception:
        return {"items": rows, "cacheStatus": "refresh_failed", "databaseCommitted": True}
    return {"items": rows, "cacheStatus": "invalidated"}
