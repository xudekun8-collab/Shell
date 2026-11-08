"""难度自适应：档位 1/2/3 对应 low/mid/high。"""
from sqlalchemy import select

from app.db.models import TrainingRecord

# 每档每题限时（秒）
TIME_LIMITS = {
    "memory_box": {1: 8, 2: 6, 3: 5},
    "category_sort": {1: 10, 2: 8, 3: 6},
}


def time_limit(game_type: str, difficulty: int) -> int:
    return TIME_LIMITS.get(game_type, {}).get(difficulty, 8)


def _clamp(level: int) -> int:
    return max(1, min(3, level))


def next_difficulty(user_id: str, game_type: str, db) -> int:
    """按最近 3 条训练记录自适应难度，返回 int 档位。"""
    rows = db.execute(
        select(TrainingRecord)
        .where(TrainingRecord.user_id == user_id, TrainingRecord.game_type == game_type)
        .order_by(TrainingRecord.created_at.desc())
        .limit(3)
    ).scalars().all()

    # 不足 3 条：返回中档，不猜
    if len(rows) < 3:
        return 2

    base = rows[0].difficulty

    # 任一放弃：降一档
    if any(r.abandoned == 1 for r in rows):
        return _clamp(base - 1)

    total_correct = sum(r.correct_count for r in rows)
    total_count = sum(r.total_count for r in rows)
    if total_count <= 0:
        return base
    accuracy = total_correct / total_count

    if accuracy < 0.60:
        return _clamp(base - 1)

    # 平均每题用时 = 总用时 / 总题数
    avg_per_question = sum(r.duration_sec for r in rows) / total_count
    if accuracy >= 0.85 and avg_per_question < time_limit(game_type, base):
        return _clamp(base + 1)

    return base
