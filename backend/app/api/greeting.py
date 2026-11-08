"""按时间主动问候接口：只读，纯规则，不调大模型。"""
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.models import Profile
from app.db.session import SessionLocal
from app.services.greeting import build_greeting, record_greeting

logger = logging.getLogger("elder_care")
router = APIRouter()


class GreetingResponse(BaseModel):
    greeting: str
    period: str


@router.get("/api/greeting/{user_id}", response_model=GreetingResponse)
def get_greeting(user_id: str, thread_id: str | None = None) -> GreetingResponse:
    with SessionLocal() as db:
        profile = db.get(Profile, user_id)
        result = build_greeting(profile)
        if thread_id and result.get("greeting"):
            try:
                record_greeting(db, user_id, thread_id, result["greeting"])
            except Exception as exc:  # 写上下文失败不影响问候返回
                db.rollback()
                logger.warning("问候写上下文失败，仍返回问候：%s", exc)
    return GreetingResponse(**result)
