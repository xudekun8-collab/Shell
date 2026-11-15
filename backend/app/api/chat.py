"""聊天接口：POST /api/chat 与 /api/chat/stream。"""
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.actions import ACTION_END, ACTION_START_GAME
from app.agent.context import recent_turns
from app.agent.graph import build_graph
from app.api.deps import require_role
from app.db.models import Conversation, InteractionEvent
from app.db.session import SessionLocal
from app.llm.client import get_client
from app.memory.compress import COMPRESS_THRESHOLD, maybe_compress
from app.memory.store import write_event_memory, write_profile

logger = logging.getLogger("elder_care")
router = APIRouter()


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    reply_text: str
    action: str
    reason: str
    available_actions: list[str]
    latency_ms: int
    params: dict | None = None


_llm_client = get_client()
_graph = build_graph(_llm_client, SessionLocal)


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: dict = Depends(require_role("elder"))) -> ChatResponse:
    started = time.perf_counter()
    user_id = user["user_id"]
    _ensure_thread_owner(user_id, request.thread_id)
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
    result = _post_memory_effects(result)

    plan = result.get("plan") or {}
    action = plan.get("action", "reply")
    reason = plan.get("reason", "")
    reply_text = result.get("reply_text", "")
    available_actions = result.get("available_actions", [action])
    params = plan.get("params") if action == "start_game" else None

    msg_count = _persist(user_id, request, result, action, reason, reply_text, latency_ms)
    if msg_count >= COMPRESS_THRESHOLD:
        maybe_compress(request.thread_id, user_id, _llm_client)
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


def _stream_gen(user_id: str, thread_id: str, text: str, recent: list[str]):
    """同一 CompiledStateGraph 的 SSE 输出；持久化在图结束后执行。"""
    started = time.perf_counter()
    initial_state = {
        "user_id": user_id,
        "thread_id": thread_id,
        "raw_input": text,
        "input_type": "text",
        "recent_dialogue": recent,
    }
    merged_state = dict(initial_state)
    first_token_at = None
    meta_sent = False

    for mode, chunk in _graph.stream(initial_state, stream_mode=["updates", "custom"]):
        if mode == "custom":
            if chunk.get("type") != "delta" or not chunk.get("text"):
                continue
            if first_token_at is None:
                first_token_at = time.perf_counter()
            yield _sse("delta", {"text": chunk["text"]})
            continue

        for node_name, update in chunk.items():
            merged_state.update(update)
            if node_name == "retrieve" and merged_state.get("intent") == ACTION_END and not meta_sent:
                yield _sse(
                    "meta",
                    {"action": ACTION_END, "reason": "用户表达结束意图", "params": None},
                )
                meta_sent = True
            elif node_name == "plan" and not meta_sent:
                plan = update.get("plan") or {}
                action = plan.get("action") or "reply"
                yield _sse(
                    "meta",
                    {
                        "action": action,
                        "reason": plan.get("reason", ""),
                        "params": plan.get("params") if action == ACTION_START_GAME else None,
                    },
                )
                meta_sent = True

    plan = merged_state.get("plan") or {}
    action = plan.get("action", "reply")
    reason = plan.get("reason", "")
    text_out = merged_state.get("reply_text", "")
    merged_state = _post_memory_effects(merged_state)

    latency_first_token_ms = int((first_token_at - started) * 1000) if first_token_at else 0
    latency_ms = int((time.perf_counter() - started) * 1000)

    msg_count = _persist(
        user_id,
        ChatRequest(thread_id=thread_id, text=text),
        merged_state,
        action,
        reason,
        text_out,
        latency_ms,
    )
    if msg_count >= COMPRESS_THRESHOLD:
        maybe_compress(thread_id, user_id, _llm_client)

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
    _ensure_thread_owner(user_id, request.thread_id)
    recent = recent_turns(user_id, request.thread_id, session_factory=SessionLocal)
    return StreamingResponse(
        _stream_gen(user_id, request.thread_id, request.text, recent),
        media_type="text/event-stream",
    )


def _ensure_thread_owner(user_id: str, thread_id: str) -> None:
    """禁止用户借用已知 thread_id 写入别人的会话。"""
    with SessionLocal() as session:
        conv = session.get(Conversation, thread_id)
        if conv is not None and conv.user_id != user_id:
            raise HTTPException(status_code=403, detail="会话不属于当前用户")


def _post_memory_effects(state: dict) -> dict:
    """图执行结束后的数据库副作用；持久化节点不进入 LangGraph。"""
    effects = list(state.get("effects") or [])
    try:
        if write_event_memory(state, SessionLocal):
            effects.append("event_memory_written")
        if write_profile(state, SessionLocal):
            effects.append("profile_updated")
    except Exception as exc:
        logger.warning("记忆写入失败：%s", exc)
    state["effects"] = effects
    return state


def _persist(user_id: str, request: ChatRequest, result: dict, action: str, reason: str, reply_text: str, latency_ms: int) -> int:
    with SessionLocal() as session:
        conv = session.get(Conversation, request.thread_id)
        if conv is None:
            conv = Conversation(id=request.thread_id, user_id=user_id, msg_count=1)
            session.add(conv)
        else:
            if conv.user_id != user_id:
                raise HTTPException(status_code=403, detail="会话不属于当前用户")
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
