"""决策规划节点：先过规则闸门，再决定是否调用模型。"""
import logging

from app.agent.actions import ACTION_END, ACTION_REPLY
from app.agent.rules import CATEGORY_NAMES, filter_actions
from app.llm.schemas import PlanParseError

logger = logging.getLogger("elder_care")


def make_plan(llm_client):
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
        return {"plan": result, "available_actions": allowed}

    return plan
