"""多轮上下文组装。"""
from sqlalchemy import select

from app.db.models import InteractionEvent
from app.db.session import SessionLocal


def recent_turns(user_id: str, thread_id: str, limit: int = 6, session_factory=None) -> list[str]:
    """取最近 limit 条对话，格式化为“老人：xxx／我：xxx”。"""
    factory = session_factory or SessionLocal
    with factory() as session:
        rows = session.execute(
            select(InteractionEvent)
            .where(InteractionEvent.user_id == user_id, InteractionEvent.thread_id == thread_id)
            .order_by(InteractionEvent.id.desc())
            .limit(limit)
        ).scalars().all()
    turns = []
    for event in reversed(rows):
        user_text = (event.raw_input or "").strip()[:40]
        reply_text = (event.reply_text or "").strip()[:40]
        turns.append(f"老人：{user_text}／我：{reply_text}")
    return turns
