"""难度自适应：档位 1/2/3 对应 low/mid/high。"""
from sqlalchemy import select

from app.db.models import TrainingRecord

# 每档每题限时（秒）
TIME_LIMITS = {
    "memory_box": {1: 8, 2: 6, 3: 5},
    "category_sort": {1: 10, 2: 8, 3: 6},
}

# 进入某档的正确率门槛：升到 2 档需 >= 0.60，升到 3 档需 >= 0.85。
# 进入与留在某档用同一把尺子：低于 ENTRY[cur] 就退出当前档。
ENTRY = {2: 0.60, 3: 0.85}


def time_limit(game_type: str, difficulty: int) -> int:
    return TIME_LIMITS.get(game_type, {}).get(difficulty, 8)


def next_difficulty(user_id: str, game_type: str, db) -> int:
    """按最近 5 条训练记录、对称门槛自适应难度，返回 int 档位。"""
    rows = db.execute(
        select(TrainingRecord)
        .where(TrainingRecord.user_id == user_id, TrainingRecord.game_type == game_type)
        .order_by(TrainingRecord.created_at.desc())
        .limit(5)
    ).scalars().all()

    # 不足 3 条：返回中档，不猜
    if len(rows) < 3:
        return 2

    cur = rows[0].difficulty

    # 放弃信号：最近 3 条里有放弃，先降一档，不再看 acc
    if cur > 1 and any(r.abandoned == 1 for r in rows[:3]):
        return cur - 1

    # 排除放弃记录后算正确率（放弃局不参与，避免双重降档）
    normal = [r for r in rows if r.abandoned != 1]
    if not normal:
        # 兜底：全部放弃，无样本，不升档，降一档；1 档保持 1
        return cur - 1 if cur > 1 else 1

    total_correct = sum(r.correct_count for r in normal)
    total_count = sum(r.total_count for r in normal)
    acc = total_correct / total_count if total_count > 0 else 0.0

    # 降档：低于当前档门槛且不是最低档
    if cur > 1 and acc < ENTRY[cur]:
        return cur - 1
    # 升档：未到最高档且达到更高一档的进入门槛
    if cur < 3 and acc >= ENTRY[cur + 1]:
        return cur + 1
    return cur
