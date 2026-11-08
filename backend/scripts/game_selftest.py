"""游戏引擎自检：记忆类 6 次提交观察难度，分类类打一局观察多题。"""
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.db.models import TrainingRecord
from app.services import game_engine


def main() -> None:
    engine = create_engine("sqlite://")
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    print("step | game_type   | difficulty | correct | total | next_difficulty")
    print("-----|-------------|------------|---------|-------|----------------")
    for step in range(1, 7):
        with factory() as db:
            start = game_engine.start("demo_user_1", "memory_box", db)
            quizzes = start["items"]["quizzes"]
        if step <= 3:
            answers = [{"index": i, "value": not q["appeared"]} for i, q in enumerate(quizzes)]
        else:
            answers = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes)]
        with factory() as db:
            result = game_engine.submit(start["session_id"], answers, 2, False, db)
        print(
            f"{step:4d} | memory_box  | {start['difficulty']:10d} | {result['correct']:7d} | "
            f"{result['total']:5d} | {result['next_difficulty']:14d}"
        )

    print()
    print("category_sort 一局自检：")
    with factory() as db:
        cat_start = game_engine.start("demo_user_1", "category_sort", db)
        cat_questions = cat_start["items"]["questions"]
    print(f"题量（questions 长度）：{len(cat_questions)}")
    bank = json.loads(Path("data/game_items/category_sort.json").read_text(encoding="utf-8"))
    id_answer = {}
    for groups in bank.values():
        for g in groups:
            id_answer[g["id"]] = g["answer"]
    cat_answers = [{"index": i, "value": id_answer[q["id"]]} for i, q in enumerate(cat_questions)]
    with factory() as db:
        cat_result = game_engine.submit(cat_start["session_id"], cat_answers, 5, False, db)
    print(f"correct={cat_result['correct']} total={cat_result['total']}")

    with factory() as db:
        count = db.execute(select(func.count()).select_from(TrainingRecord)).scalar()
    print(f"写入训练记录条数：{count}")


if __name__ == "__main__":
    main()
