"""游戏会话：只放内存，不落库；服务重启会丢失（已知局限）。"""
import time
import uuid

_SESSIONS = {}
_TTL_SECONDS = 30 * 60  # 30 分钟未提交视为过期


def create(user_id: str, game_type: str, difficulty: int, payload: dict) -> str:
    """创建会话；同一用户新 start 覆盖旧会话。"""
    cleanup()
    for sid in list(_SESSIONS):
        if _SESSIONS[sid]["user_id"] == user_id:
            _SESSIONS.pop(sid, None)
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = {
        "user_id": user_id,
        "game_type": game_type,
        "difficulty": difficulty,
        "payload": payload,
        "started_at": time.time(),
    }
    return session_id


def get(session_id: str):
    return _SESSIONS.get(session_id)


def drop(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def cleanup() -> None:
    now = time.time()
    for sid in list(_SESSIONS):
        if now - _SESSIONS[sid]["started_at"] > _TTL_SECONDS:
            _SESSIONS.pop(sid, None)
