"""规则闸门：在模型之前执行，纯 Python 实现，不交给模型判断。"""
from datetime import datetime
from pathlib import Path

import yaml

from app.agent.actions import ACTION_END, ACTION_REMIND, ACTION_REPLY, ALL_ACTIONS
from app.db.session import to_time

END_KEYWORDS = ["不聊了", "再见", "拜拜", "晚安", "不说了", "就这样吧"]

_SAFETY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "safety_rules.yaml"
_SAFETY_DATA = yaml.safe_load(_SAFETY_PATH.read_text(encoding="utf-8"))
SAFETY_TEMPLATES = _SAFETY_DATA["templates"]
SAFETY_RULES = _SAFETY_DATA["rules"]

CATEGORY_NAMES = {
    "medical": "医疗",
    "finance": "金融",
    "legal": "法律",
    "bereavement": "丧亲哀伤",
    "crisis": "情绪危机",
}


def _rule_matches(rule: dict, raw: str) -> bool:
    if not any(k in raw for k in (rule.get("keywords") or [])):
        return False
    for word in rule.get("exclude") or []:
        if word in raw:
            return False
    require = rule.get("require_any") or []
    if require and not any(w in raw for w in require):
        return False
    return True


def match_safety(raw: str) -> dict | None:
    """命中安全规则时返回 severity 最高的一条（含话术），未命中返回 None。"""
    best = None
    for rule in SAFETY_RULES:
        if _rule_matches(rule, raw):
            if best is None or rule["severity"] > best["severity"]:
                best = rule
    if best is None:
        return None
    return {
        "category": best["category"],
        "severity": best["severity"],
        "template": SAFETY_TEMPLATES[best["template_key"]],
    }


def _in_sleep_window(profile: dict | None, now=None) -> bool:
    """判断当前时间是否落在 sleep_time 到 wake_time 之间，跨夜按跨夜处理。"""
    if not profile:
        return False
    try:
        sleep = to_time(profile.get("sleep_time"))
        wake = to_time(profile.get("wake_time"))
    except (TypeError, ValueError):
        return False
    if now is None:
        now = datetime.now().time()
    if sleep > wake:
        return now >= sleep or now <= wake
    return sleep <= now <= wake


def filter_actions(state: dict, now=None) -> tuple[list[str], str | None, dict | None]:
    """返回 (allowed, forced, safety)。安全规则最优先强制 reply，R1 结束语强制 end，R2 睡眠窗口剔除 remind。"""
    allowed = list(ALL_ACTIONS)
    raw = state.get("raw_input", "") or ""

    safety = match_safety(raw)
    if safety:
        return [ACTION_REPLY], ACTION_REPLY, safety

    if any(k in raw for k in END_KEYWORDS):
        return [ACTION_END], ACTION_END, None

    if _in_sleep_window(state.get("profile"), now):
        allowed = [a for a in allowed if a != ACTION_REMIND]

    return allowed, None, None
