"""家属端：邀请码绑定 + 只读三接口（概览 / 记录 / 告警）。"""
import logging
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app import config
from app.api.deps import current_user, require_role
from app.db.models import Conversation, FamilyBind, InteractionEvent, TrainingRecord
from app.db.session import SessionLocal
from app.services.token import create_token

logger = logging.getLogger("elder_care")
router = APIRouter()

INVITE_TTL_HOURS = 24


class InviteResponse(BaseModel):
    invite_code: str
    expires_at: str


class BindRequest(BaseModel):
    invite_code: str


class BindResponse(BaseModel):
    token: str
    elder_id: str


def _elder_for_family(db, family_user_id: str) -> str | None:
    row = db.execute(
        select(FamilyBind)
        .where(FamilyBind.family_user_id == family_user_id)
        .order_by(FamilyBind.bound_at.desc())
        .limit(1)
    ).scalars().first()
    return row.elder_id if row else None


@router.post("/api/family/invite", response_model=InviteResponse)
def create_invite(user: dict = Depends(current_user)) -> InviteResponse:
    """老人生成 6 位邀请码，24 小时内有效。"""
    code = f"{random.randint(0, 999999):06d}"
    expires = datetime.now() + timedelta(hours=INVITE_TTL_HOURS)
    with SessionLocal() as db:
        db.add(FamilyBind(elder_id=user["user_id"], invite_code=code, expires_at=expires))
        db.commit()
    return InviteResponse(invite_code=code, expires_at=expires.strftime("%Y-%m-%d %H:%M:%S"))


@router.post("/api/family/bind", response_model=BindResponse)
def bind(request: BindRequest, user: dict = Depends(current_user)) -> BindResponse:
    """家属凭邀请码绑定老人，成功后换发 role=family 的 token。"""
    if not config.AUTH_SECRET:
        raise HTTPException(status_code=500, detail="AUTH_SECRET 未配置")
    now = datetime.now()
    with SessionLocal() as db:
        row = db.execute(
            select(FamilyBind).where(
                FamilyBind.invite_code == request.invite_code,
                FamilyBind.family_user_id.is_(None),
                FamilyBind.expires_at > now,
            )
        ).scalars().first()
        if row is None:
            raise HTTPException(status_code=400, detail="邀请码无效或已过期")
        row.family_user_id = user["user_id"]
        row.bound_at = now
        elder_id = row.elder_id
        db.commit()
    token = create_token(user["user_id"], "family", config.AUTH_SECRET)
    return BindResponse(token=token, elder_id=elder_id)


@router.get("/api/family/overview")
def family_overview(user: dict = Depends(require_role("family"))):
    """今天聊了几轮、最近训练、最近摘要。"""
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"])
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        today = datetime.now().date()
        day_start = datetime(today.year, today.month, today.day)
        chat_count = db.execute(
            select(func.count()).select_from(InteractionEvent).where(
                InteractionEvent.user_id == elder_id,
                InteractionEvent.input_type != "greeting",
                InteractionEvent.created_at >= day_start,
            )
        ).scalar() or 0
        last_record = db.execute(
            select(TrainingRecord)
            .where(TrainingRecord.user_id == elder_id)
            .order_by(TrainingRecord.created_at.desc())
            .limit(1)
        ).scalars().first()
        last_conv = db.execute(
            select(Conversation)
            .where(Conversation.user_id == elder_id, Conversation.summary.isnot(None))
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        ).scalars().first()
        last_training = None
        if last_record:
            last_training = {
                "game_type": last_record.game_type,
                "correct_count": last_record.correct_count,
                "total_count": last_record.total_count,
                "created_at": last_record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        summary = last_conv.summary if last_conv else None
    return {
        "elder_id": elder_id,
        "today_chat_count": chat_count,
        "last_training": last_training,
        "last_summary": summary,
    }


@router.get("/api/family/records")
def family_records(user: dict = Depends(require_role("family"))):
    """最近 30 天训练记录与正确率。"""
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"])
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        since = datetime.now() - timedelta(days=30)
        rows = db.execute(
            select(TrainingRecord)
            .where(TrainingRecord.user_id == elder_id, TrainingRecord.created_at >= since)
            .order_by(TrainingRecord.created_at.desc())
        ).scalars().all()
        records = [
            {
                "game_type": r.game_type,
                "difficulty": r.difficulty,
                "correct_count": r.correct_count,
                "total_count": r.total_count,
                "duration_sec": r.duration_sec,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for r in rows
        ]
        valid = [r for r in rows if r.total_count > 0]
        avg_accuracy = (
            round(sum(r.correct_count / r.total_count for r in valid) / len(valid) * 100)
            if valid
            else 0
        )
    return {"elder_id": elder_id, "records": records, "total": len(rows), "avg_accuracy": avg_accuracy}


@router.get("/api/family/alerts")
def family_alerts(user: dict = Depends(require_role("family"))):
    """severity=3 情绪危机告警 + 多日未互动提醒。"""
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"])
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        rows = db.execute(
            select(InteractionEvent)
            .where(InteractionEvent.user_id == elder_id)
            .order_by(InteractionEvent.created_at.desc())
            .limit(200)
        ).scalars().all()
        alerts = []
        for event in rows:
            effects = (event.perceived or {}).get("effects") or []
            if "safety_crisis_3" in effects:
                alerts.append(
                    {
                        "type": "crisis",
                        "detail": "情绪危机告警（severity=3）",
                        "created_at": event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
        last_event = rows[0].created_at if rows else None
        if last_event is None or (datetime.now() - last_event).days >= 2:
            alerts.append(
                {
                    "type": "inactive",
                    "detail": "多日未互动",
                    "last_interaction": last_event.strftime("%Y-%m-%d %H:%M:%S") if last_event else None,
                }
            )
    return {"elder_id": elder_id, "alerts": alerts}
