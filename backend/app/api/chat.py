"""聊天接口：POST /api/chat。"""
import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.context import recent_turns
from app.agent.graph import build_graph
from app.db.models import Conversation, InteractionEvent
from app.db.session import SessionLocal
from app.llm.client import get_client
from app.memory.compress import COMPRESS_THRESHOLD, maybe_compress

logger = logging.getLogger("elder_care")
router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str
    thread_id: str
    text: str


class ChatResponse(BaseModel):
    reply_text: str
    action: str
    reason: str
    available_actions: list[str]
    latency_ms: int


_llm_client = get_client()
_graph = build_graph(_llm_client, SessionLocal)


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    recent = recent_turns(request.user_id, request.thread_id)
    result = _graph.invoke(
        {
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "raw_input": request.text,
            "input_type": "text",
            "recent_dialogue": recent,
        }
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    plan = result.get("plan") or {}
    action = plan.get("action", "reply")
    reason = plan.get("reason", "")
    reply_text = result.get("reply_text", "")
    available_actions = result.get("available_actions", [action])

    msg_count = _persist(request, result, action, reason, reply_text, latency_ms)
    if msg_count >= COMPRESS_THRESHOLD:
        maybe_compress(request.thread_id, _llm_client)
    logger.info("用户 %s 本轮动作 %s，耗时 %sms", request.user_id, action, latency_ms)
    return ChatResponse(
        reply_text=reply_text,
        action=action,
        reason=reason,
        available_actions=available_actions,
        latency_ms=latency_ms,
    )


def _persist(request: ChatRequest, result: dict, action: str, reason: str, reply_text: str, latency_ms: int) -> int:
    with SessionLocal() as session:
        conv = session.get(Conversation, request.thread_id)
        if conv is None:
            conv = Conversation(id=request.thread_id, user_id=request.user_id, msg_count=1)
            session.add(conv)
        else:
            conv.user_id = request.user_id
            conv.msg_count += 1
        session.add(
            InteractionEvent(
                user_id=request.user_id,
                thread_id=request.thread_id,
                input_type="text",
                raw_input=request.text,
                perceived={
                    "intent": result.get("intent"),
                    "emotion": result.get("emotion"),
                    "effects": result.get("effects"),
                },
                action=action,
                reason=reason,
                reply_text=reply_text,
                latency_ms=latency_ms,
            )
        )
        session.commit()
        return conv.msg_count
