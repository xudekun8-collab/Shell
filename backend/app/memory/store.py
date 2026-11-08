"""三层记忆：事件记忆写入、画像更新与召回。"""
import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.db.models import Memory, Profile
from app.db.session import SessionLocal
from app.memory.scoring import overlap_score, score_memory, sort_scored, time_prefilter

logger = logging.getLogger("elder_care")

EVENT_TRIGGERS = ["来看我", "来看您", "打电话", "去了", "买了", "吃了", "做了", "生日", "过节", "昨天", "前天", "上周", "上个月"]

_FAMILY_KEYWORDS = ["来看我", "来看您", "来看", "孙女", "孙子", "儿子", "女儿", "老伴", "家人", "亲戚"]
_DISCOMFORT_KEYWORDS = ["不舒服", "难受", "疼", "头晕", "感冒", "生病", "咳嗽", "发烧"]
_FESTIVAL_KEYWORDS = ["生日", "过节", "过年", "中秋", "端午", "春节", "重阳", "国庆"]

FOLLOWUP_KEYWORDS = ["提过", "说过", "上次", "之前", "记得", "啥时候", "那次"]

_SEPARATORS = "，。！？、；,.;!? \t\n"


def _importance(raw: str) -> int:
    if any(k in raw for k in _FAMILY_KEYWORDS) or any(k in raw for k in _DISCOMFORT_KEYWORDS):
        return 5
    if any(k in raw for k in _FESTIVAL_KEYWORDS):
        return 4
    return 3


def _occurred_at(raw: str) -> date:
    today = date.today()
    if "前天" in raw:
        return today - timedelta(days=2)
    if "昨天" in raw:
        return today - timedelta(days=1)
    if "上个月" in raw:
        return today - timedelta(days=30)
    if "上周末" in raw:
        return today - timedelta(days=7)
    if "上周" in raw:
        return today - timedelta(days=7)
    return today


def write_event_memory(state: dict, session_factory=None) -> bool:
    """命中触发词时，从 raw_input 抽一条不超过 50 字的事件记忆写入。"""
    raw = (state.get("raw_input") or "").strip()
    user_id = state.get("user_id")
    if not user_id or not raw or not any(t in raw for t in EVENT_TRIGGERS):
        return False
    factory = session_factory or SessionLocal
    with factory() as session:
        session.add(
            Memory(
                user_id=user_id,
                layer="event",
                content=raw[:50],
                importance=_importance(raw),
                occurred_at=_occurred_at(raw),
            )
        )
        session.commit()
    return True


def _extract_clause(text: str, start: int) -> str:
    rest = text[start:]
    end = len(rest)
    for i, ch in enumerate(rest):
        if ch in _SEPARATORS:
            end = i
            break
    return rest[:end].strip()[:20]


def _profile_updates(raw: str) -> dict:
    updates = {}
    for trigger in ("叫我", "我姓"):
        idx = raw.find(trigger)
        if idx != -1:
            val = _extract_clause(raw, idx + len(trigger))
            if val:
                updates["nickname"] = val
            break
    taboos = []
    for trigger in ("我不喜欢", "别提", "不要说"):
        idx = raw.find(trigger)
        if idx != -1:
            val = _extract_clause(raw, idx + len(trigger))
            if val:
                taboos.append(val)
    if taboos:
        updates["taboos"] = taboos
    interests = []
    start = 0
    while True:
        idx = raw.find("我喜欢", start)
        if idx == -1:
            break
        if idx == 0 or raw[idx - 1] != "不":
            val = _extract_clause(raw, idx + len("我喜欢"))
            if val:
                interests.append(val)
        start = idx + 1
    if interests:
        updates["interests"] = interests
    return updates


def write_profile(state: dict, session_factory=None) -> bool:
    """命中“叫我/我姓/我喜欢/我不喜欢/别提/不要说”时更新画像，追加去重不覆盖。"""
    raw = (state.get("raw_input") or "").strip()
    user_id = state.get("user_id")
    updates = _profile_updates(raw)
    if not user_id or not updates:
        return False
    factory = session_factory or SessionLocal
    with factory() as session:
        profile = session.get(Profile, user_id)
        if profile is None:
            return False
        if updates.get("nickname"):
            profile.nickname = updates["nickname"]
        for key in ("interests", "taboos"):
            if updates.get(key):
                merged = list(getattr(profile, key) or [])
                for item in updates[key]:
                    if item not in merged:
                        merged.append(item)
                setattr(profile, key, merged)
        session.commit()
    return True


def score_candidate(query: str, content: str, importance: int, occurred_at, layer: str, weights=None, filter_time: bool = False):
    """按召回规则计算有效分数 (score, importance)；不满足候选条件返回 None。"""
    if filter_time and not time_prefilter(query or "", occurred_at):
        return None
    followup = any(k in (query or "") for k in FOLLOWUP_KEYWORDS)
    if layer == "session":
        # session 只在字面相关时进候选，importance 统一按 3，occurred_at 为空按 30 天
        if overlap_score(query or "", content) == 0:
            return None
        eff_importance = 3
        eff_occurred_at = occurred_at or (date.today() - timedelta(days=30))
    else:
        if overlap_score(query or "", content) == 0 and not followup:
            return None
        eff_importance = importance
        eff_occurred_at = occurred_at
    score = score_memory(query or "", content, eff_importance, eff_occurred_at, layer, weights=weights)
    return score, eff_importance


def recall(user_id: str, query: str, top_k: int = 3, session_factory=None, weights=None) -> list[dict]:
    """召回事件与 session 记忆，按可解释打分排序；不满足候选条件的不进。"""
    factory = session_factory or SessionLocal
    with factory() as session:
        rows = session.execute(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.layer.in_(("event", "session")),
                Memory.is_deleted == 0,
            )
        ).scalars().all()
        scored = []
        for m in rows:
            res = score_candidate(query or "", m.content, m.importance, m.occurred_at, m.layer, weights=weights, filter_time=True)
            if res is None:
                continue
            s, imp = res
            scored.append((m, s, imp))
        ranked = sort_scored(scored)
        return [
            {
                "memory_id": m.id,
                "content": m.content,
                "importance": m.importance,
                "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
                "score": round(s, 4),
            }
            for m, s, _ in ranked[:top_k]
        ]
