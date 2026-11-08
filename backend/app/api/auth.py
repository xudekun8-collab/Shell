"""登录接口：微信静默换 openid 与演示后门。"""
import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config
from app.db.models import Profile, User
from app.db.session import SessionLocal
from app.services.token import create_token

logger = logging.getLogger("elder_care")
router = APIRouter()


class WxLoginRequest(BaseModel):
    code: str


class DemoLoginRequest(BaseModel):
    user_id: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    nickname: str
    role: str


def _ensure_user(db, user_id: str) -> Profile:
    """首次登录建 users + profile，二次登录不重复建。"""
    if db.get(User, user_id) is None:
        db.add(User(id=user_id))
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, nickname="您好", interests=[], taboos=[])
        db.add(profile)
    db.commit()
    return profile


def _issue(user_id: str, role: str) -> AuthResponse:
    if not config.AUTH_SECRET:
        raise HTTPException(status_code=500, detail="AUTH_SECRET 未配置")
    token = create_token(user_id, role, config.AUTH_SECRET)
    return AuthResponse(token=token, user_id=user_id, nickname=user_id, role=role)


@router.post("/api/auth/wx", response_model=AuthResponse)
def wx_login(request: WxLoginRequest) -> AuthResponse:
    if not config.WX_APPID or not config.WX_SECRET:
        raise HTTPException(status_code=500, detail="微信登录未配置")
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": config.WX_APPID,
        "secret": config.WX_SECRET,
        "js_code": request.code,
        "grant_type": "authorization_code",
    }
    try:
        data = httpx.get(url, params=params, timeout=10).json()
    except Exception as exc:
        logger.warning("微信 jscode2session 调用失败：%s", exc)
        raise HTTPException(status_code=502, detail="微信登录服务不可用")
    if "openid" not in data:
        raise HTTPException(status_code=401, detail="微信登录失败")
    user_id = "wx_" + data["openid"][:20]
    with SessionLocal() as db:
        profile = _ensure_user(db, user_id)
        nickname = profile.nickname
    return _issue_with_nickname(user_id, nickname)


def _issue_with_nickname(user_id: str, nickname: str) -> AuthResponse:
    if not config.AUTH_SECRET:
        raise HTTPException(status_code=500, detail="AUTH_SECRET 未配置")
    token = create_token(user_id, "elder", config.AUTH_SECRET)
    return AuthResponse(token=token, user_id=user_id, nickname=nickname, role="elder")


@router.post("/api/auth/demo", response_model=AuthResponse)
def demo_login(request: DemoLoginRequest) -> AuthResponse:
    if config.DEMO_MODE != "1":
        raise HTTPException(status_code=401, detail="演示登录未开启")
    user_id = request.user_id or "demo_user_1"
    with SessionLocal() as db:
        profile = _ensure_user(db, user_id)
        nickname = profile.nickname
    return _issue_with_nickname(user_id, nickname)
