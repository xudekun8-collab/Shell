"""记东西：先展示物品，再判断目标是否出现过。"""
import random

from app.services.games._data import load

TIME_LIMIT = {1: 8, 2: 6, 3: 5}
QUESTION_COUNT = {1: 4, 2: 6, 3: 8}
LEVELS = {1: "low", 2: "mid", 3: "high"}
_last_used = {}


def generate(difficulty: int, n: int, user_id: str = "") -> dict:
    groups = load("memory_box")[LEVELS[difficulty]]
    key = (user_id, "memory_box")
    last = _last_used.get(key)
    candidates = [group for group in groups if group["id"] != last] or groups
    group = random.choice(candidates)
    _last_used[key] = group["id"]

    questions = []
    for quiz in group["quizzes"]:
        questions.append(
            {
                **quiz,
                "correct_text": quiz["target"] + ("（有）" if quiz["appeared"] else "（没有）"),
            }
        )
    items = {
        "show_items": group["show_items"],
        "quizzes": [
            {"target": quiz["target"], "appeared": quiz["appeared"]}
            for quiz in group["quizzes"]
        ],
    }
    return {"items": items, "payload": {"questions": questions}}


def judge(quiz: dict, answer) -> bool:
    return bool(answer) == bool(quiz["appeared"])
