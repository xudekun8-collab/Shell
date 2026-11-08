"""游戏引擎：开始游戏与提交判分。"""
import json
import random
from pathlib import Path

from app.db.models import TrainingRecord
from app.services import game_session
from app.services.difficulty import next_difficulty, time_limit

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "game_items"
_GAME_FILES = {"memory_box": "memory_box.json", "category_sort": "category_sort.json"}
_LEVELS = {1: "low", 2: "mid", 3: "high"}

# 同一用户同一类型最近用过的组 id，避免连续重复
_last_used = {}


def _load(game_type: str) -> dict:
    path = _DATA_DIR / _GAME_FILES[game_type]
    return json.loads(path.read_text(encoding="utf-8"))


def start(user_id: str, game_type: str, db) -> dict:
    difficulty = next_difficulty(user_id, game_type, db)
    groups = _load(game_type)[_LEVELS[difficulty]]
    last = _last_used.get((user_id, game_type))
    candidates = [g for g in groups if g["id"] != last] or groups
    group = random.choice(candidates)
    _last_used[(user_id, game_type)] = group["id"]

    session_id = game_session.create(user_id, game_type, difficulty, group)

    if game_type == "memory_box":
        items = {"show_items": group["show_items"], "quizzes": group["quizzes"]}
    else:
        items = {"word": group["word"], "options": group["options"]}

    return {
        "session_id": session_id,
        "game_type": game_type,
        "difficulty": difficulty,
        "time_limit_sec": time_limit(game_type, difficulty),
        "items": items,
    }


def submit(session_id: str, answers: list, duration_sec: int, abandoned: bool, db) -> dict:
    session = game_session.get(session_id)
    if session is None:
        raise ValueError("会话已失效，请重新开始")

    group = session["group"]
    user_id = session["user_id"]
    game_type = session["game_type"]
    difficulty = session["difficulty"]

    duration = min(max(int(duration_sec or 0), 0), 600)
    answer_map = {a.get("index"): a.get("value") for a in (answers or [])}

    if game_type == "memory_box":
        quizzes = group["quizzes"]
        total = len(quizzes)
        correct = sum(
            1 for i, q in enumerate(quizzes)
            if i in answer_map and bool(answer_map[i]) == bool(q["appeared"])
        )
    else:
        total = 1
        correct = 1 if (0 in answer_map and answer_map[0] == group["answer"]) else 0

    db.add(
        TrainingRecord(
            user_id=user_id,
            game_type=game_type,
            difficulty=difficulty,
            correct_count=correct,
            total_count=total,
            duration_sec=duration,
            abandoned=1 if abandoned else 0,
        )
    )
    db.commit()

    next_diff = next_difficulty(user_id, game_type, db)
    game_session.drop(session_id)

    accuracy = round(correct / total, 4) if total else 0.0
    summary_text = (
        f"这次完成了 {total} 题，答对 {correct} 题，用时 {duration} 秒。\n"
        "本结果只用于调整练习难度，不作为任何健康判断。"
    )
    return {
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "next_difficulty": next_diff,
        "summary_text": summary_text,
    }
