"""老人画像编辑接口。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_role
from app.db.models import Profile
from app.db.session import SessionLocal

router = APIRouter()


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=32)
    interests: list[str] | None = None
    taboos: list[str] | None = None


class ProfileResponse(BaseModel):
    nickname: str
    interests: list[str]
    taboos: list[str]


def clean_tags(items: list[str]) -> list[str]:
    result = []
    for item in items or []:
        value = str(item).strip()[:20]
        if value and value not in result:
            result.append(value)
    return result[:30]


@router.put("/api/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    user: dict = Depends(require_role("elder")),
) -> ProfileResponse:
    """老人修改自己的称呼、兴趣习惯与忌讳。"""
    with SessionLocal() as db:
        profile = db.get(Profile, user["user_id"])
        if profile is None:
            raise HTTPException(status_code=404, detail="画像不存在")
        if payload.nickname is not None:
            nickname = payload.nickname.strip()
            if not nickname:
                raise HTTPException(status_code=400, detail="称呼不能为空")
            profile.nickname = nickname[:32]
        if payload.interests is not None:
            profile.interests = clean_tags(payload.interests)
        if payload.taboos is not None:
            profile.taboos = clean_tags(payload.taboos)
        db.commit()
        return ProfileResponse(
            nickname=profile.nickname,
            interests=profile.interests or [],
            taboos=profile.taboos or [],
        )
