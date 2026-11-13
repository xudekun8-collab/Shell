"""聊天接口：POST /api/chat 与 /api/chat/stream。"""
import json
import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.actions import ACTION_END, ACTION_REPLY, ACTION_START_GAME
from app.agent.context import recent_turns
from app.agent.graph import build_graph
from app.agent.nodes.act import make_act
from app.agent.nodes.perceive import make_perceive
from app.agent.nodes.plan import make_plan
from app.agent.nodes.retrieve import make_retrieve
from app.api.deps import require_role
from app.db.models import Conversation, InteractionEvent
from app.db.session import SessionLocal
from app.llm.client import get_client
from app.memory.compress import COMPRESS_THRESHOLD, maybe_compress

logger = logging.getLogger("elder_care")
router = APIRouter()


class ChatRequest(BaseModel):
    thread_id: str
    text: str


class ChatResponse(BaseModel):
    reply_text: str
    action: str
    reason: str
    available_actions: list[str]
    latency_ms: int
    params: dict | None = None


_llm_client = get_client()
_graph = build_graph(_llm_client, SessionLocal)
_perceive = make_perceive(SessionLocal)
_retrieve = make_retrieve(SessionLocal)
_plan = make_plan(_llm_client, SessionLocal)
_act = make_act(_llm_client, SessionLocal)


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: dict = Depends(require_role("elder"))) -> ChatResponse:
    started = time.perf_counter()
    user_id = user["user_id"]
    recent = recent_turns(user_id, request.thread_id, session_factory=SessionLocal)
    result = _graph.invoke(
        {
            "user_id": user_id,
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
    params = plan.get("params") if action == "start_game" else None

    msg_count = _persist(user_id, request, result, action, reason, reply_text, latency_ms)
    if msg_count >= COMPRESS_THRESHOLD:
        maybe_compress(request.thread_id, _llm_client)
    logger.info("用户 %s 本轮动作 %s，耗时 %sms", user_id, action, latency_ms)
    return ChatResponse(
        reply_text=reply_text,
        action=action,
        reason=reason,
        available_actions=available_actions,
        latency_ms=latency_ms,
        params=params,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _step(fn, state: dict) -> dict:
    merged = dict(state)
    merged.update(fn(state))
    return merged


def _stream_gen(user_id: str, thread_id: str, text: str, recent: list[str]):
    """同步生成器；单用户演示可接受占用事件循环，不做 async 化。"""
    started = time.perf_counter()
    state = {
        "user_id": user_id,
        "thread_id": thread_id,
        "raw_input": text,
        "input_type": "text",
        "recent_dialogue": recent,
    }
    state = _step(_perceive, state)
    state = _step(_retrieve, state)
    if state.get("intent") == ACTION_END:
        state["plan"] = {"action": ACTION_END, "reason": "用户表达结束意图", "params": {}}
    else:
        state = _step(_plan, state)

    plan = state.get("plan") or {}
    action = plan.get("action") or ACTION_REPLY
    reason = plan.get("reason", "")
    safety = (plan.get("params") or {}).get("safety")
    first_token_at = None

    meta_params = plan.get("params") if action == ACTION_START_GAME else None
    yield _sse("meta", {"action": action, "reason": reason, "params": meta_params})

    if action == ACTION_REPLY and not safety:
        acc = []
        try:
            for piece in _llm_client.reply_stream(state, plan):
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                acc.append(piece)
                yield _sse("delta", {"text": piece})
        except Exception as exc:
            logger.warning("流式回复中断：%s", exc)
        text_out = "".join(acc)
        plan.setdefault("params", {})["reply_text"] = text_out
        state["plan"] = plan
        state = _step(_act, state)
    else:
        state = _step(_act, state)
        text_out = state.get("reply_text", "")
        first_token_at = time.perf_counter()
        yield _sse("delta", {"text": text_out})

    latency_first_token_ms = int((first_token_at - started) * 1000) if first_token_at else 0
    latency_ms = int((time.perf_counter() - started) * 1000)

    msg_count = _persist(
        user_id,
        ChatRequest(thread_id=thread_id, text=text),
        state,
        action,
        reason,
        text_out,
        latency_ms,
    )
    if msg_count >= COMPRESS_THRESHOLD:
        maybe_compress(thread_id, _llm_client)

    yield _sse(
        "done",
        {
            "latency_first_token_ms": latency_first_token_ms,
            "latency_ms": latency_ms,
            "action": action,
        },
    )


@router.post("/api/chat/stream")
def chat_stream(request: ChatRequest, user: dict = Depends(require_role("elder"))):
    user_id = user["user_id"]
    recent = recent_turns(user_id, request.thread_id, session_factory=SessionLocal)
    return StreamingResponse(
        _stream_gen(user_id, request.thread_id, request.text, recent),
        media_type="text/event-stream",
    )


def _persist(user_id: str, request: ChatRequest, result: dict, action: str, reason: str, reply_text: str, latency_ms: int) -> int:
    with SessionLocal() as session:
        conv = session.get(Conversation, request.thread_id)
        if conv is None:
            conv = Conversation(id=request.thread_id, user_id=user_id, msg_count=1)
            session.add(conv)
        else:
            conv.user_id = user_id
            conv.msg_count += 1
        session.add(
            InteractionEvent(
                user_id=user_id,
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
