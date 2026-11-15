"""执行交互节点：把 plan 转成中文回复并输出增量 token。"""
import logging

from langgraph.config import get_stream_writer

from app.agent.actions import (
    ACTION_END,
    ACTION_REMIND,
    ACTION_REPLY,
    ACTION_START_ASSESSMENT,
    ACTION_START_GAME,
    ACTION_SUGGEST_REST,
)

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

_GAME_REPLIES = {
    "memory_box": "咱们玩个记东西的小游戏，就当活动活动脑子。",
    "category_sort": "咱们把东西分一分类",
    "number_seq": "咱们看一串数字，再慢慢回想一下。",
    "common_sense": "咱们做几个生活常识题，看看日常怎么更稳妥。",
}


def make_act(llm_client):
    def act(state: dict) -> dict:
        # 图内只产生流事件和最终 state；数据库副作用由 API 在图结束后统一处理。
        writer = get_stream_writer()
        plan = state.get("plan")
        if not plan or state.get("intent") == ACTION_END:
            plan = {"action": ACTION_END, "reason": "用户表达结束意图", "params": {}}
        action = plan.get("action") or ACTION_REPLY
        params = plan.get("params") or {}
        if action == ACTION_END:
            text = END_REPLY_TEXT
            writer({"type": "delta", "text": text})
        elif action == ACTION_START_GAME:
            text = _GAME_REPLIES.get(params.get("game_type"), _ACTION_REPLIES[ACTION_START_GAME])
            writer({"type": "delta", "text": text})
        elif action == ACTION_REPLY:
            if params.get("reply_text"):
                text = params["reply_text"]
                writer({"type": "delta", "text": text})
            else:
                pieces = []
                try:
                    if llm_client:
                        for piece in llm_client.reply_stream(state, plan):
                            if piece:
                                pieces.append(piece)
                                writer({"type": "delta", "text": piece})
                except Exception as exc:
                    logger.warning("流式回复生成失败：%s", exc)
                text = "".join(pieces)
                if not text:
                    text = _ACTION_REPLIES[ACTION_REPLY]
                    writer({"type": "delta", "text": text})
        else:
            text = _ACTION_REPLIES.get(action, _ACTION_REPLIES[ACTION_REPLY])
            writer({"type": "delta", "text": text})

        effects = [action]
        if (params.get("safety") or {}).get("severity") == 3:
            effects.append("safety_crisis_3")

        updates = {"plan": plan, "reply_text": text, "effects": effects}
        if state.get("intent") == ACTION_END:
            updates["available_actions"] = [ACTION_END]
        return updates

    return act
