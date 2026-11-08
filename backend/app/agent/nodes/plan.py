"""决策规划节点：先过规则闸门，再决定是否调用模型。"""
import logging

from sqlalchemy import select

from app.agent.actions import ACTION_END, ACTION_REPLY, ACTION_START_GAME
from app.agent.rules import CATEGORY_NAMES, filter_actions
from app.db.models import TrainingRecord
from app.llm.schemas import PlanParseError
from app.services.difficulty import next_difficulty

logger = logging.getLogger("elder_care")


def _resolve_game_type(raw: str, user_id: str, session) -> str:
    if any(k in raw for k in ("记东西", "记忆", "记住")):
        return "memory_box"
    if any(k in raw for k in ("分一分", "分类", "归类")):
        return "category_sort"
    last = session.execute(
        select(TrainingRecord)
        .where(TrainingRecord.user_id == user_id)
        .order_by(TrainingRecord.created_at.desc())
        .limit(1)
    ).scalars().first()
    if last and last.game_type == "memory_box":
        return "category_sort"
    return "memory_box"


def _game_params(state: dict, session_factory) -> dict:
    raw = state.get("raw_input", "") or ""
    user_id = state.get("user_id")
    with session_factory() as session:
        game_type = _resolve_game_type(raw, user_id, session)
        difficulty = next_difficulty(user_id, game_type, session)
    return {"game_type": game_type, "difficulty": difficulty}


def make_plan(llm_client, session_factory):
    def plan(state: dict) -> dict:
        allowed, forced, safety = filter_actions(state)
        if forced == ACTION_END:
            result = {"action": ACTION_END, "reason": "用户表达结束意图", "params": {}}
        elif forced == ACTION_REPLY:
            category_name = CATEGORY_NAMES.get(safety["category"], safety["category"])
            result = {
                "action": ACTION_REPLY,
                "reason": f"命中{category_name}安全规则",
                "params": {
                    "reply_text": safety["template"],
                    "safety": {"category": safety["category"], "severity": safety["severity"]},
                },
            }
        else:
            try:
                result = llm_client.plan(state)
            except PlanParseError as exc:
                logger.warning("模型输出解析失败，降级为普通回复：%s", exc)
                result = {"action": ACTION_REPLY, "reason": "模型输出解析失败", "params": {}}
            except Exception as exc:
                logger.warning("模型调用失败，降级为普通回复：%s", exc)
                result = {"action": ACTION_REPLY, "reason": "模型调用失败", "params": {}}
            if result.get("action") not in allowed:
                logger.warning("模型返回动作 %s 不在白名单内，降级为 reply", result.get("action"))
                result = {"action": ACTION_REPLY, "reason": "动作不在白名单，降级为回复", "params": {}}
            if result.get("action") == ACTION_START_GAME:
                result["params"] = _game_params(state, session_factory)
        return {"plan": result, "available_actions": allowed}

    return plan
