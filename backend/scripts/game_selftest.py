"""游戏引擎自检：固定种子模拟四类游戏各 20 局。"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.db.models import TrainingRecord
from app.services import game_engine, game_session
from app.services.games import GAME_REGISTRY

SEED = 20261108
ROUNDS = 20
MODELS = {"strong": 0.90, "normal": 0.70, "weak": 0.45}
BASE_TIME = datetime(2026, 1, 1, 12, 0, 0)


def _wrong_value(question: dict) -> str:
    if "appeared" in question:
        return not question["appeared"]
    answer = question["answer"]
    if "digits" in question:
        return str(int(answer[0]) % 9 + 1) + answer[1:]
    return next(option for option in question["options"] if option != answer)


def main() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    print(f"seed={SEED} rounds={ROUNDS}")
    print("game_type     | model  | final | last5_avg | total_correct / total")
    print("--------------|--------|-------|-----------|---------------------")
    failures = []
    for game_type in GAME_REGISTRY:
        for model, probability in MODELS.items():
            rng = random.Random(SEED)
            user_id = f"selftest_{game_type}_{model}"
            difficulties = []
            correct_sum = 0
            total_sum = 0
            for round_index in range(ROUNDS):
                with factory() as db:
                    start = game_engine.start(user_id, game_type, db)
                questions = game_session.get(start["session_id"])["payload"]["questions"]
                difficulties.append(start["difficulty"])
                answers = []
                for index, question in enumerate(questions):
                    if rng.random() < probability:
                        value = (
                            question["appeared"]
                            if "appeared" in question
                            else question["correct_text"]
                        )
                    else:
                        value = _wrong_value(question)
                    answers.append({"index": index, "value": value})
                with factory() as db:
                    result = game_engine.submit(start["session_id"], answers, 20, False, db)
                    record = db.execute(
                        select(TrainingRecord)
                        .where(TrainingRecord.user_id == user_id)
                        .order_by(TrainingRecord.id.desc())
                        .limit(1)
                    ).scalar_one()
                    record.created_at = BASE_TIME + timedelta(minutes=round_index)
                    db.commit()
                correct_sum += result["correct"]
                total_sum += result["total"]
                final = result["next_difficulty"]
            last5 = round(sum(difficulties[-5:]) / 5, 2)
            expected = {"strong": 3, "normal": 2, "weak": 1}[model]
            if final != expected:
                failures.append((game_type, model, final, expected))
            print(
                f"{game_type:13s} | {model:6s} | {final:5d} | {last5:9.2f} | "
                f"{correct_sum:13d} / {total_sum}"
            )
    if failures:
        print("收敛失败：", failures)
        raise SystemExit(1)
    print("四类游戏 strong=3 normal=2 weak=1 全部通过")


if __name__ == "__main__":
    main()
