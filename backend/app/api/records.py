"""训练记录查询接口。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.api.deps import require_demo_token
from app.db.models import TrainingRecord
from app.db.session import SessionLocal

router = APIRouter()


class RecordItem(BaseModel):
    game_type: str
    difficulty: int
    correct_count: int
    total_count: int
    duration_sec: int
    created_at: str


class Summary(BaseModel):
    total: int
    avg_accuracy: int
    total_duration: int
    by_type: list[dict]


class RecordsResponse(BaseModel):
    records: list[RecordItem]
    summary: Summary


@router.get(
    "/api/records/{user_id}",
    response_model=RecordsResponse,
    dependencies=[Depends(require_demo_token)],
)
def get_records(user_id: str, limit: int = 20) -> RecordsResponse:
    limit = max(1, min(limit, 50))
    with SessionLocal() as db:
        all_rows = db.execute(
            select(TrainingRecord).where(TrainingRecord.user_id == user_id)
        ).scalars().all()
        valid = [r for r in all_rows if r.total_count > 0]
        avg_accuracy = (
            round(sum(r.correct_count / r.total_count for r in valid) / len(valid) * 100)
            if valid
            else 0
        )
        by_type_rows = db.execute(
            select(
                TrainingRecord.game_type,
                func.count(),
                func.avg(
                    case(
                        (TrainingRecord.total_count > 0, TrainingRecord.correct_count * 100.0 / TrainingRecord.total_count),
                        else_=None,
                    )
                ),
            )
            .where(TrainingRecord.user_id == user_id)
            .group_by(TrainingRecord.game_type)
        ).all()
        by_type = [
            {"game_type": gt, "total": cnt, "avg_accuracy": round(avg_acc or 0)}
            for gt, cnt, avg_acc in by_type_rows
        ]
        recent = db.execute(
            select(TrainingRecord)
            .where(TrainingRecord.user_id == user_id)
            .order_by(TrainingRecord.created_at.desc())
            .limit(limit)
        ).scalars().all()
        records = [
            RecordItem(
                game_type=r.game_type,
                difficulty=r.difficulty,
                correct_count=r.correct_count,
                total_count=r.total_count,
                duration_sec=r.duration_sec,
                created_at=r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for r in recent
        ]
    return RecordsResponse(
        records=records,
        summary=Summary(
            total=len(all_rows),
            avg_accuracy=avg_accuracy,
            total_duration=sum(r.duration_sec for r in all_rows),
            by_type=by_type,
        ),
    )
