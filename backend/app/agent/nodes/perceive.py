"""感知节点：关键词解析意图与情绪，并从数据库读取任务上下文。"""
from app.agent.rules import END_KEYWORDS
from app.db.models import Conversation

GAME_KEYWORDS = ["游戏", "玩", "猜谜", "算数", "记词"]
REST_KEYWORDS = ["休息", "累", "困", "睡觉"]

_EMOTION_RULES = [
    ("低落", ["难过", "伤心", "孤独", "想哭", "不开心"]),
    ("焦虑", ["担心", "害怕", "紧张", "着急"]),
    ("开心", ["高兴", "开心", "真好", "舒服"]),
]


def _intent(text: str) -> str:
    if any(k in text for k in END_KEYWORDS):
        return "end"
    if any(k in text for k in GAME_KEYWORDS):
        return "game"
    if any(k in text for k in REST_KEYWORDS):
        return "rest"
    return "chat"


def _emotion(text: str) -> tuple[str, float]:
    for name, keywords in _EMOTION_RULES:
        if any(k in text for k in keywords):
            score = 0.9 if name in ("低落", "焦虑") else 0.8
            return name, score
    return "平静", 0.5


def make_perceive(session_factory):
    def perceive(state: dict) -> dict:
        text = state.get("raw_input", "") or ""
        intent = _intent(text)
        emotion, score = _emotion(text)
        task_context = None
        thread_id = state.get("thread_id")
        if thread_id:
            with session_factory() as session:
                conv = session.get(Conversation, thread_id)
                task_context = conv.open_items if conv else None
        return {
            "intent": intent,
            "emotion": emotion,
            "emotion_score": score,
            "task_context": task_context,
        }

    return perceive
