"""会话摘要压缩：消息数超阈值时压缩为摘要与未完成事项。"""
import logging

from sqlalchemy import select

from app.db.models import Conversation, InteractionEvent
from app.db.session import SessionLocal

logger = logging.getLogger("elder_care")

COMPRESS_THRESHOLD = 8

_compress_count = 0


def maybe_compress(thread_id: str, llm_client, session_factory=None) -> bool:
    """msg_count 达到阈值时做累积压缩；失败回滚并返回 False。"""
    global _compress_count
    factory = session_factory or SessionLocal
    with factory() as session:
        conv = session.get(Conversation, thread_id)
        if conv is None or conv.msg_count < COMPRESS_THRESHOLD:
            return False
        rows = session.execute(
            select(InteractionEvent)
            .where(InteractionEvent.thread_id == thread_id)
            .order_by(InteractionEvent.id.desc())
            .limit(COMPRESS_THRESHOLD)
        ).scalars().all()
        events = list(rows)[::-1]
        dialogue = [f"{e.raw_input}｜{e.reply_text}" for e in events]
        old_summary = conv.summary or ""
        logger.info("开始压缩 thread=%s，消息数=%s，取最近 %s 条", thread_id, conv.msg_count, len(dialogue))
        try:
            result = llm_client.summarize(dialogue, previous_summary=old_summary)
            summary = (result.get("summary") or "").strip()[:100]
            new_open = [str(x) for x in (result.get("open_items") or [])]
            merged_open = []
            for item in list(conv.open_items or []) + new_open:
                if item not in merged_open:
                    merged_open.append(item)
            conv.summary = summary
            conv.open_items = merged_open
            conv.msg_count = 0
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("压缩失败已回滚 thread=%s：%s", thread_id, exc)
            return False
        _compress_count += 1
        logger.info("第 %s 次压缩完成 thread=%s，摘要字数=%s", _compress_count, thread_id, len(summary))
        return True
