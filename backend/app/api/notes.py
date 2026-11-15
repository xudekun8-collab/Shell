"""老人端读取家属留言。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import require_role
from app.db.models import FamilyNote
from app.db.session import SessionLocal

router = APIRouter()


class UnreadNote(BaseModel):
    id: int
    text: str


class NotesResponse(BaseModel):
    unread_count: int
    note: UnreadNote | None


class NoteReadResponse(BaseModel):
    read: bool


@router.get("/api/notes", response_model=NotesResponse)
def get_notes(user: dict = Depends(require_role("elder"))) -> NotesResponse:
    """只返回最近一条未读留言和未读总数。"""
    with SessionLocal() as db:
        unread_count = db.execute(
            select(func.count())
            .select_from(FamilyNote)
            .where(
                FamilyNote.elder_id == user["user_id"],
                FamilyNote.read_at.is_(None),
            )
        ).scalar() or 0
        latest = db.execute(
            select(FamilyNote)
            .where(
                FamilyNote.elder_id == user["user_id"],
                FamilyNote.read_at.is_(None),
            )
            .order_by(FamilyNote.created_at.desc(), FamilyNote.id.desc())
            .limit(1)
        ).scalars().first()
    note = UnreadNote(id=latest.id, text=latest.text) if latest else None
    return NotesResponse(unread_count=unread_count, note=note)


@router.post("/api/notes/{note_id}/read", response_model=NoteReadResponse)
def mark_note_read(
    note_id: int,
    user: dict = Depends(require_role("elder")),
) -> NoteReadResponse:
    """老人读完后标记；重复调用保持幂等。"""
    with SessionLocal() as db:
        note = db.get(FamilyNote, note_id)
        if note is None or note.elder_id != user["user_id"]:
            raise HTTPException(status_code=404, detail="留言不存在")
        if note.read_at is None:
            note.read_at = datetime.now()
            db.commit()
    return NoteReadResponse(read=True)
