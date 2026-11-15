"""生活常识判断：按生活场景选择合适做法。"""
import random

from app.services.games._data import load

TIME_LIMIT = {1: 10, 2: 8, 3: 6}
QUESTION_COUNT = {1: 6, 2: 8, 3: 10}
LEVELS = {1: "low", 2: "mid", 3: "high"}


def generate(difficulty: int, n: int, user_id: str = "") -> dict:
    chosen = random.sample(load("common_sense")[LEVELS[difficulty]], n)
    return {
        "items": {
            "questions": [
                {
                    "id": question["id"],
                    "question": question["question"],
                    "options": question["options"],
                }
                for question in chosen
            ]
        },
        "payload": {
            "questions": [
                {
                    **question,
                    "correct_text": question["answer"],
                }
                for question in chosen
            ]
        },
    }


def judge(quiz: dict, answer) -> bool:
    return answer == quiz["answer"]
