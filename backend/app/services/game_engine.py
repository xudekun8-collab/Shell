"""游戏引擎：只负责会话、注册表调度与训练记录。"""

from app.db.models import TrainingRecord
from app.services import game_session
from app.services.difficulty import next_difficulty, time_limit
from app.services.games import get_game


def start(user_id: str, game_type: str, db, difficulty: int | None = None) -> dict:
    game = get_game(game_type)
    # 传了档位就用传进来的（来自智能体的 plan 节点），没传才自己按历史记录算
    if difficulty is None:
        difficulty = next_difficulty(user_id, game_type, db)
    count = game.QUESTION_COUNT[difficulty]
    generated = game.generate(difficulty, count, user_id)
    payload = generated["payload"]
    items = generated["items"]

    session_id = game_session.create(user_id, game_type, difficulty, payload)

    return {
        "session_id": session_id,
        "game_type": game_type,
        "difficulty": difficulty,
        "time_limit_sec": time_limit(game_type, difficulty),
        "items": items,
    }


def submit(session_id: str, answers: list, duration_sec: int, abandoned: bool, db, expect_user_id: str | None = None) -> dict:
    session = game_session.get(session_id)
    if session is None:
        raise ValueError("会话已失效，请重新开始")
    if expect_user_id is not None and session["user_id"] != expect_user_id:
        raise PermissionError("会话不属于当前用户")

    payload = session["payload"]
    user_id = session["user_id"]
    game_type = session["game_type"]
    difficulty = session["difficulty"]
    game = get_game(game_type)

    duration = min(max(int(duration_sec or 0), 0), 600)
    answer_map = {a.get("index"): a.get("value") for a in (answers or [])}

    questions = payload["questions"]
    total = len(questions)
    details = []
    correct = 0
    for index, question in enumerate(questions):
        is_correct = index in answer_map and game.judge(question, answer_map[index])
        correct += int(is_correct)
        details.append(
            {
                "index": index,
                "correct": is_correct,
                "correct_text": question["correct_text"],
                "explanation": "" if is_correct else question.get("explanation", ""),
            }
        )

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
        "details": details,
    }
