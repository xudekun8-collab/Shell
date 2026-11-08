"""模拟用户实验台：用固定随机种子验证难度自适应收敛。"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.db.models import TrainingRecord
from app.services.difficulty import next_difficulty

SEED = 20261108
GAME_TYPE = "category_sort"
QUESTION_COUNT = {1: 6, 2: 8, 3: 10}
GAMES_PER_MODEL = 20

# 能力模型：每题答对概率
MODELS = {"strong": 0.90, "normal": 0.70, "weak": 0.45}
EXPECTED_LEVEL = {"strong": 3, "normal": 2, "weak": 1}

RESULT_PATH = Path(__file__).resolve().parent.parent / "data" / "experiment_result.json"

# 固定基准时间，保证 created_at 有序且可复现
BASE_TIME = datetime(2026, 1, 1, 12, 0, 0)


def _new_factory():
    engine = create_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def run_simulation(seed: int = SEED, factory=None) -> dict:
    """返回轨迹、正确率、摘要与收敛判定。"""
    if factory is None:
        factory = _new_factory()

    trajectories = {}
    accuracies = {}
    summary = {}
    convergence = {}

    for name, p in MODELS.items():
        rng = random.Random(seed)
        user_id = f"sim_{name}"
        diffs = []
        accs = []
        for game_index in range(GAMES_PER_MODEL):
            with factory() as db:
                difficulty = next_difficulty(user_id, GAME_TYPE, db)
            total = QUESTION_COUNT[difficulty]
            correct = sum(1 for _ in range(total) if rng.random() < p)
            diffs.append(difficulty)
            accs.append(correct / total)
            with factory() as db:
                db.add(
                    TrainingRecord(
                        user_id=user_id,
                        game_type=GAME_TYPE,
                        difficulty=difficulty,
                        correct_count=correct,
                        total_count=total,
                        duration_sec=total * 3,
                        abandoned=0,
                        created_at=BASE_TIME + timedelta(minutes=game_index),
                    )
                )
                db.commit()

        trajectories[name] = diffs
        accuracies[name] = accs
        final = diffs[-1]
        first5 = round(sum(diffs[:5]) / 5, 2)
        last5 = round(sum(diffs[-5:]) / 5, 2)
        summary[name] = {
            "final_difficulty": final,
            "last5_avg": last5,
            "first5_avg": first5,
        }
        if name == "strong":
            ok = final == 3
        elif name == "weak":
            ok = final == 1
        else:
            ok = abs(last5 - 2) <= 0.5
        convergence[name] = ok

    return {
        "seed": seed,
        "models": summary,
        "convergence": convergence,
        "trajectories": trajectories,
        "accuracies": accuracies,
    }


def _write_experiment(result: dict) -> None:
    payload = {
        "simulation": {
            "seed": result["seed"],
            "models": result["models"],
            "convergence": result["convergence"],
        },
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    result = run_simulation()
    print("难度轨迹（每局档位）：")
    for name in MODELS:
        print(f"{name}: {' '.join(str(d) for d in result['trajectories'][name])}")
    print()
    for name in MODELS:
        s = result["models"][name]
        print(
            f"{name}: 前5局平均 {s['first5_avg']}，后5局平均 {s['last5_avg']}，"
            f"收尾档位 {s['final_difficulty']}，收敛 {result['convergence'][name]}"
        )
    _write_experiment(result)
    if not all(result["convergence"].values()):
        print("收敛判定失败：", result["convergence"])
        raise SystemExit(1)
    print("收敛判定全部通过")


if __name__ == "__main__":
    main()
