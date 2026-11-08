"""鉴权依赖：从 token 解析当前用户，或校验可选口令。"""
import logging
import os

from fastapi import Depends, Header, HTTPException

from app import config
from app.services.token import decode_token

logger = logging.getLogger("elder_care")


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """解析 Authorization: Bearer <token>，失败一律 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:].strip()
    if not config.AUTH_SECRET:
        raise HTTPException(status_code=401, detail="鉴权未配置")
    try:
        payload = decode_token(token, config.AUTH_SECRET)
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效")
    return {"user_id": payload["user_id"], "role": payload.get("role", "elder")}


def require_role(role: str):
    """返回一个要求指定角色的依赖。"""

    def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="无权限")
        return user

    return _dep


def legacy_path_allowed() -> None:
    """旧版带 user_id 的路径只在演示模式放行，生产模式 403 并记日志。"""
    if config.DEMO_MODE != "1":
        logger.warning("旧版带 user_id 的接口在生产模式被拒绝")
        raise HTTPException(status_code=403, detail="旧接口已关闭")


def require_demo_token(x_demo_token: str | None = Header(default=None)) -> None:
    """可选的 X-Demo-Token 口令校验，未设置时完全放行。"""
    token = os.getenv("DEMO_TOKEN", "").strip()
    if not token:
        return
    if x_demo_token != token:
        raise HTTPException(status_code=401, detail="未授权的访问")
