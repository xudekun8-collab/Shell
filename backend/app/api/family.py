"""家属端：邀请码绑定 + 只读三接口（概览 / 记录 / 告警）。"""
import logging
import secrets
from datetime import datetime, timedelta
from ipaddress import ip_address

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app import config
from app.api.deps import require_role
from app.api.records import completed_rows
from app.db.models import (
    BindAttempt,
    Conversation,
    FamilyBind,
    FamilyNote,
    InteractionEvent,
    Profile,
    TrainingRecord,
)
from app.db.session import SessionLocal
from app.services.token import create_token

logger = logging.getLogger("elder_care")
router = APIRouter()

INVITE_TTL_HOURS = 24
MAX_INVITES_PER_24_HOURS = 3
MAX_BIND_FAILURES_PER_DAY = 5


class InviteResponse(BaseModel):
    invite_code: str
    expires_at: str


class BindRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=16)


class BindResponse(BaseModel):
    token: str
    elder_id: str


class FamilyNoteRequest(BaseModel):
    text: str = Field(max_length=1000)


class FamilyNoteItem(BaseModel):
    id: int
    text: str
    created_at: str
    read: bool


class FamilyNoteList(BaseModel):
    notes: list[FamilyNoteItem]


class FamilyInterestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100)


class FamilyInterestResponse(BaseModel):
    interests: list[str]


def _elder_for_family(db, family_user_id: str, for_update: bool = False) -> str | None:
    query = (
        select(FamilyBind)
        .where(FamilyBind.family_user_id == family_user_id)
        .order_by(FamilyBind.bound_at.desc())
        .limit(1)
    )
    if for_update:
        query = query.with_for_update()
    row = db.execute(query).scalars().first()
    return row.elder_id if row else None


def _record_bind_failure(db, ip_key: str, day) -> None:
    attempt = db.get(BindAttempt, (ip_key, day))
    if attempt is None:
        attempt = BindAttempt(user_id=ip_key, day=day, fail_count=1)
        db.add(attempt)
    else:
        attempt.fail_count += 1
    db.commit()


def _client_ip(http_request: Request) -> str:
    if config.TRUST_PROXY_HEADERS:
        candidate = http_request.headers.get("x-real-ip", "").strip()
        if not candidate:
            forwarded = http_request.headers.get("x-forwarded-for", "")
            candidate = forwarded.split(",", 1)[0].strip()
        if candidate:
            try:
                return str(ip_address(candidate))
            except ValueError:
                logger.warning("绑定请求携带了不合法的代理 IP")
    return http_request.client.host if http_request.client else "unknown"


@router.post("/api/family/invite", response_model=InviteResponse)
def create_invite(user: dict = Depends(require_role("elder"))) -> InviteResponse:
    """老人生成 8 位邀请码，24 小时内有效。"""
    now = datetime.now()
    expires = now + timedelta(hours=INVITE_TTL_HOURS)
    with SessionLocal() as db:
        recent_count = db.execute(
            select(func.count())
            .select_from(FamilyBind)
            .where(
                FamilyBind.elder_id == user["user_id"],
                FamilyBind.created_at >= now - timedelta(hours=24),
            )
        ).scalar() or 0
        if recent_count >= MAX_INVITES_PER_24_HOURS:
            raise HTTPException(
                status_code=429,
                detail="今天已经发过好几次了，让家人用最早那个",
            )
        code = None
        for _ in range(5):
            candidate = f"{secrets.randbelow(10**8):08d}"
            conflict = db.execute(
                select(FamilyBind.id)
                .where(
                    FamilyBind.invite_code == candidate,
                    FamilyBind.family_user_id.is_(None),
                    FamilyBind.expires_at > now,
                )
                .limit(1)
            ).scalar_one_or_none()
            if conflict is None:
                code = candidate
                break
        if code is None:
            raise HTTPException(status_code=500, detail="邀请码生成失败，请再试一次")
        db.add(FamilyBind(elder_id=user["user_id"], invite_code=code, expires_at=expires))
        db.commit()
    return InviteResponse(invite_code=code, expires_at=expires.strftime("%Y-%m-%d %H:%M:%S"))


@router.post("/api/family/bind", response_model=BindResponse)
def bind(payload: BindRequest, http_request: Request) -> BindResponse:
    """家属凭邀请码绑定老人，成功后换发 role=family 的 token。"""
    if not config.AUTH_SECRET:
        raise HTTPException(status_code=500, detail="AUTH_SECRET 未配置")
    now = datetime.now()
    day = now.date()
    ip_key = "ip:" + _client_ip(http_request)
    with SessionLocal() as db:
        attempt = db.get(BindAttempt, (ip_key, day))
        if attempt is not None and attempt.fail_count >= MAX_BIND_FAILURES_PER_DAY:
            raise HTTPException(status_code=429, detail="试的次数太多了，过一会再试")
        fam_id = "family_" + secrets.token_hex(4)
        result = db.execute(
            update(FamilyBind)
            .where(
                FamilyBind.invite_code == payload.invite_code,
                FamilyBind.family_user_id.is_(None),
                FamilyBind.expires_at > now,
            )
            .values(family_user_id=fam_id, bound_at=now)
        )
        if result.rowcount != 1:
            db.rollback()
            _record_bind_failure(db, ip_key, day)
            raise HTTPException(status_code=400, detail="邀请码无效或已用过")
        row = db.execute(
            select(FamilyBind).where(
                FamilyBind.invite_code == payload.invite_code,
                FamilyBind.family_user_id == fam_id,
            )
        ).scalars().one()
        elder_id = row.elder_id
        if attempt is None:
            db.add(BindAttempt(user_id=ip_key, day=day, fail_count=0))
        else:
            attempt.fail_count = 0
        db.commit()
    token = create_token(fam_id, "family", config.AUTH_SECRET)
    return BindResponse(token=token, elder_id=elder_id)


@router.post("/api/family/note", response_model=FamilyNoteItem)
def create_note(
    payload: FamilyNoteRequest,
    user: dict = Depends(require_role("family")),
) -> FamilyNoteItem:
    """家属给已绑定老人留一句最多 60 字的话。"""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="写一句话再发")
    if len(text) > 60:
        raise HTTPException(status_code=400, detail="话太长了，短一点")
    now = datetime.now()
    day_start = datetime(now.year, now.month, now.day)
    day_end = day_start + timedelta(days=1)
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"], for_update=True)
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        today_count = db.execute(
            select(func.count())
            .select_from(FamilyNote)
            .where(
                FamilyNote.family_user_id == user["user_id"],
                FamilyNote.created_at >= day_start,
                FamilyNote.created_at < day_end,
            )
        ).scalar() or 0
        if today_count >= 3:
            raise HTTPException(status_code=429, detail="今天已经留过话了")
        note = FamilyNote(
            elder_id=elder_id,
            family_user_id=user["user_id"],
            text=text,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
    return FamilyNoteItem(
        id=note.id,
        text=note.text,
        created_at=note.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        read=False,
    )


@router.get("/api/family/notes", response_model=FamilyNoteList)
def family_notes(user: dict = Depends(require_role("family"))) -> FamilyNoteList:
    """当前家属最近留下的 5 句话。"""
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"])
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        rows = db.execute(
            select(FamilyNote)
            .where(
                FamilyNote.elder_id == elder_id,
                FamilyNote.family_user_id == user["user_id"],
            )
            .order_by(FamilyNote.created_at.desc(), FamilyNote.id.desc())
            .limit(5)
        ).scalars().all()
    return FamilyNoteList(
        notes=[
            FamilyNoteItem(
                id=row.id,
                text=row.text,
                created_at=row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                read=row.read_at is not None,
            )
            for row in rows
        ]
    )


@router.post("/api/family/interest", response_model=FamilyInterestResponse)
def add_elder_interest(
    payload: FamilyInterestRequest,
    user: dict = Depends(require_role("family")),
) -> FamilyInterestResponse:
    """家属为绑定老人追加一个兴趣或生活习惯。"""
    text = payload.text.strip()[:20]
    if not text:
        raise HTTPException(status_code=400, detail="请写一个兴趣或习惯")
    with SessionLocal() as db:
        elder_id = _elder_for_family(db, user["user_id"])
        if not elder_id:
            raise HTTPException(status_code=404, detail="未绑定老人")
        profile = db.get(Profile, elder_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="画像不存在")
        interests = list(profile.interests or [])
        if text not in interests:
            interests.append(text)
        profile.interests = interests[:30]
        db.commit()
        return FamilyInterestResponse(interests=profile.interests or [])


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
                "abandoned": r.abandoned,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for r in rows
        ]
        completed = completed_rows(rows)
        avg_accuracy = (
            round(sum(r.correct_count / r.total_count for r in completed) / len(completed) * 100)
            if completed
            else 0
        )
    return {
        "elder_id": elder_id,
        "records": records,
        "total": len(completed),
        "avg_accuracy": avg_accuracy,
    }


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
