"""执行交互节点：把 plan 转成中文回复，并在收尾写入记忆。"""
import logging

from app.agent.actions import (
    ACTION_END,
    ACTION_REMIND,
    ACTION_REPLY,
    ACTION_START_ASSESSMENT,
    ACTION_START_GAME,
    ACTION_SUGGEST_REST,
)
from app.memory.store import write_event_memory, write_profile

logger = logging.getLogger("elder_care")

END_REPLY_TEXT = "好的，我随时都在，您多保重，下次再聊。"

_ACTION_REPLIES = {
    ACTION_REPLY: "您说，我听着呢。",
    ACTION_START_GAME: "好，我们来玩个小游戏，活动活动脑筋。",
    ACTION_START_ASSESSMENT: "我们来做个小测评，看看最近的状态。",
    ACTION_SUGGEST_REST: "您先歇一歇，喝口水，别累着自己。",
    ACTION_REMIND: "提醒您：按时吃饭、按时休息，照顾好自己。",
    ACTION_END: END_REPLY_TEXT,
}


def make_act(session_factory):
    def act(state: dict) -> dict:
        plan = state.get("plan")
        if not plan or state.get("intent") == ACTION_END:
            plan = {"action": ACTION_END, "reason": "用户表达结束意图", "params": {}}
        action = plan.get("action") or ACTION_REPLY
        params = plan.get("params") or {}
        if action == ACTION_END:
            text = END_REPLY_TEXT
        elif action == ACTION_REPLY and params.get("reply_text"):
            text = params["reply_text"]
        else:
            text = _ACTION_REPLIES.get(action, _ACTION_REPLIES[ACTION_REPLY])

        effects = [action]
        if (params.get("safety") or {}).get("severity") == 3:
            effects.append("safety_crisis_3")
        try:
            if write_event_memory(state, session_factory):
                effects.append("event_memory_written")
            if write_profile(state, session_factory):
                effects.append("profile_updated")
        except Exception as exc:
            logger.warning("记忆写入失败：%s", exc)

        updates = {"plan": plan, "reply_text": text, "effects": effects}
        if state.get("intent") == ACTION_END:
            updates["available_actions"] = [ACTION_END]
        return updates

    return act
