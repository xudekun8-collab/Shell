"""可解释的记忆打分函数，权重放顶部便于消融实验。"""
from datetime import date, timedelta

WEIGHTS = {"overlap": 0.55, "importance": 0.04, "type": 0.08}
TYPE_WEIGHT = {"event": 1.0, "session": 0.8}
TIME_FILTER_WINDOW = 2
TIE_BREAK_GAP = 0.03

_SEPARATORS = "，。！？、；,.;!? \t\n"

_TIME_WORDS = [
    ("上周末", 7),
    ("上周三", 4),
    ("上周", 7),
    ("上个月", 30),
    ("下个月", -30),
    ("前天", 2),
    ("昨天", 1),
    ("今天", 0),
]


def _bigrams(text: str) -> set:
    cleaned = "".join(ch for ch in text if ch not in _SEPARATORS)
    if len(cleaned) < 2:
        return {cleaned}
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def overlap_score(query: str, content: str) -> float:
    """query 与 content 的字符二元组 Jaccard。"""
    a = _bigrams(query or "")
    b = _bigrams(content or "")
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def parse_time_offset(query: str) -> int | None:
    """解析 query 里的时间词，返回“距今多少天”的偏移；解析不出返回 None。"""
    for word, offset in _TIME_WORDS:
        if word in (query or ""):
            return offset
    return None


def time_prefilter(query: str, occurred_at, window_days: int = TIME_FILTER_WINDOW) -> bool:
    """时间粗筛：query 有时间词时，记忆 occurred_at 需落在目标日期附近；否则保留。"""
    offset = parse_time_offset(query)
    if offset is None or occurred_at is None:
        return True
    target = date.today() - timedelta(days=offset)
    return abs((target - occurred_at).days) <= window_days


def importance_score(importance: int) -> float:
    return (importance or 0) / 5.0


def type_score(layer: str) -> float:
    return TYPE_WEIGHT.get(layer, 1.0)


def score_memory(query, content, importance, occurred_at, layer="event", weights=None) -> float:
    """加权打分：0.55 重合度 + 0.04 重要性 + 0.08 类型（时间项已降级为粗筛）。"""
    w = dict(WEIGHTS)
    if weights:
        w.update(weights)
    return (
        w["overlap"] * overlap_score(query, content)
        + w["importance"] * importance_score(importance)
        + w["type"] * type_score(layer)
    )


def score_breakdown(query, content, importance, occurred_at, layer="event", weights=None) -> dict:
    """返回各分项的加权值，供附录说明排序原因。"""
    w = dict(WEIGHTS)
    if weights:
        w.update(weights)
    return {
        "overlap": round(w["overlap"] * overlap_score(query, content), 4),
        "time": 0.0,
        "importance": round(w["importance"] * importance_score(importance), 4),
        "type": round(w["type"] * type_score(layer), 4),
        "total": round(score_memory(query, content, importance, occurred_at, layer, weights=weights), 4),
    }


def sort_scored(scored):
    """scored: [(item, score, importance)]；整体降序，分数差 < TIE_BREAK_GAP 时 importance 高者优先。"""
    from functools import cmp_to_key

    def cmp(a, b):
        _, score_a, imp_a = a
        _, score_b, imp_b = b
        if abs(score_a - score_b) < TIE_BREAK_GAP:
            return (imp_b > imp_a) - (imp_b < imp_a)
        return (score_b > score_a) - (score_b < score_a)

    return sorted(scored, key=cmp_to_key(cmp))
