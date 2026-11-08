"""记忆查询与删除接口。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import require_demo_token
from app.db.models import Conversation, Memory, Profile
from app.db.session import SessionLocal

router = APIRouter()


class EventMemory(BaseModel):
    memory_id: int
    layer: str
    content: str
    importance: int
    occurred_at: str | None


class SessionMemory(BaseModel):
    thread_id: str
    layer: str
    content: str
    open_items: list


class MemoryLayersResponse(BaseModel):
    profile: dict | None
    events: list[EventMemory]
    sessions: list[SessionMemory]


class DeleteResponse(BaseModel):
    deleted: bool


@router.get(
    "/api/memories/{user_id}",
    response_model=MemoryLayersResponse,
    dependencies=[Depends(require_demo_token)],
)
def get_memories(user_id: str) -> MemoryLayersResponse:
    with SessionLocal() as session:
        profile = session.get(Profile, user_id)
        profile_data = None
        if profile:
            profile_data = {
                "layer": "profile",
                "nickname": profile.nickname,
                "interests": profile.interests or [],
                "taboos": profile.taboos or [],
            }
        events = session.execute(
            select(Memory)
            .where(Memory.user_id == user_id, Memory.layer == "event", Memory.is_deleted == 0)
            .order_by(Memory.id.desc())
        ).scalars().all()
        event_data = [
            EventMemory(
                memory_id=m.id,
                layer=m.layer,
                content=m.content,
                importance=m.importance,
                occurred_at=m.occurred_at.isoformat() if m.occurred_at else None,
            )
            for m in events
        ]
        sessions = session.execute(
            select(Conversation).where(Conversation.user_id == user_id)
        ).scalars().all()
        session_data = [
            SessionMemory(thread_id=c.id, layer="session", content=c.summary or "", open_items=c.open_items or [])
            for c in sessions
        ]
    return MemoryLayersResponse(profile=profile_data, events=event_data, sessions=session_data)


@router.delete(
    "/api/memories/{user_id}/{memory_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_demo_token)],
)
def delete_memory(user_id: str, memory_id: int) -> DeleteResponse:
    with SessionLocal() as session:
        memory = session.get(Memory, memory_id)
        if memory is None or memory.user_id != user_id or memory.is_deleted == 1:
            raise HTTPException(status_code=404, detail="记忆不存在")
        memory.is_deleted = 1
        session.commit()
    return DeleteResponse(deleted=True)
