"""按时间主动问候接口：只读，纯规则，不调大模型。"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import legacy_path_allowed, require_role
from app.db.models import Profile
from app.db.session import SessionLocal
from app.services.greeting import build_greeting, record_greeting

logger = logging.getLogger("elder_care")
router = APIRouter()


class GreetingResponse(BaseModel):
    greeting: str
    period: str


def _greeting(user_id: str, thread_id: str | None) -> GreetingResponse:
    with SessionLocal() as db:
        profile = db.get(Profile, user_id)
        result = build_greeting(profile)
        if thread_id and result.get("greeting"):
            try:
                record_greeting(db, user_id, thread_id, result["greeting"])
            except Exception as exc:
                db.rollback()
                logger.warning("问候写上下文失败，仍返回问候：%s", exc)
    return GreetingResponse(**result)


@router.get("/api/greeting", response_model=GreetingResponse)
def get_greeting(user: dict = Depends(require_role("elder")), thread_id: str | None = None) -> GreetingResponse:
    return _greeting(user["user_id"], thread_id)


@router.get("/api/greeting/{user_id}", response_model=GreetingResponse)
def get_greeting_legacy(user_id: str, thread_id: str | None = None) -> GreetingResponse:
    legacy_path_allowed()
    return _greeting(user_id, thread_id)
