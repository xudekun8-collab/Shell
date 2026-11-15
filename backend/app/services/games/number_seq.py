"""数字工作记忆：展示数字串后从四个同位数选项中选出原串。"""
import random

from app.services.games._data import load

TIME_LIMIT = {1: 12, 2: 10, 3: 8}
QUESTION_COUNT = {1: 6, 2: 8, 3: 10}
LEVELS = {1: "low", 2: "mid", 3: "high"}


def _distractor(length: int, answer: str, used: set[str]) -> str:
    while True:
        value = str(random.randint(1, 9)) + "".join(
            str(random.randint(0, 9)) for _ in range(length - 1)
        )
        if value != answer and value not in used:
            used.add(value)
            return value


def generate(difficulty: int, n: int, user_id: str = "") -> dict:
    bank = load("number_seq")[LEVELS[difficulty]]
    chosen = random.sample(bank, n)
    items = []
    questions = []
    for question in chosen:
        answer = question["digits"]
        used = {answer}
        options = [answer] + [_distractor(len(answer), answer, used) for _ in range(3)]
        random.shuffle(options)
        items.append(
            {
                "id": question["id"],
                "digits": answer,
                "show_ms": 3000,
                "options": options,
            }
        )
        questions.append(
            {
                **question,
                "show_ms": 3000,
                "options": options,
                "answer": answer,
                "correct_text": answer,
            }
        )
    return {"items": {"questions": items}, "payload": {"questions": questions}}


def judge(quiz: dict, answer) -> bool:
    return answer == quiz["answer"]
