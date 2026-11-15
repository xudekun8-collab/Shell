"""分分类：从同一档题库中抽题并判断分类。"""
import random

from app.services.games._data import load

TIME_LIMIT = {1: 10, 2: 8, 3: 6}
QUESTION_COUNT = {1: 6, 2: 8, 3: 10}
LEVELS = {1: "low", 2: "mid", 3: "high"}
_last_used = {}


def generate(difficulty: int, n: int, user_id: str = "") -> dict:
    groups = load("category_sort")[LEVELS[difficulty]]
    key = (user_id, "category_sort")
    used = _last_used.get(key, set())
    unused = [group for group in groups if group["id"] not in used]
    chosen = random.sample(unused, min(n, len(unused)))
    if len(chosen) < n:
        backfill = [group for group in groups if group["id"] in used]
        chosen += random.sample(backfill, n - len(chosen))
    _last_used[key] = {group["id"] for group in chosen}

    return {
        "items": {
            "questions": [
                {"id": group["id"], "word": group["word"], "options": group["options"]}
                for group in chosen
            ]
        },
        "payload": {
            "questions": [
                {
                    **group,
                    "correct_text": group["answer"],
                }
                for group in chosen
            ]
        },
    }


def judge(quiz: dict, answer) -> bool:
    return answer == quiz["answer"]
