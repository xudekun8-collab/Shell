"""游戏引擎自检：6 次提交（3 次极低正确率接 3 次高正确率）观察难度自适应。"""
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

    with factory() as db:
        count = db.execute(select(func.count()).select_from(TrainingRecord)).scalar()
    print(f"写入训练记录条数：{count}")


if __name__ == "__main__":
    main()
