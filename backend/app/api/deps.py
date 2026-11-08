"""请求头校验依赖：演示期可选的简易 token，默认关闭。"""
import os

from fastapi import Header, HTTPException


def require_demo_token(x_demo_token: str | None = Header(default=None)) -> None:
    """校验 X-Demo-Token 请求头。

    读环境变量 DEMO_TOKEN：未设置或为空时完全放行（保持现状，不影响演示）；
    设置后要求请求头 X-Demo-Token 与之一致，否则返回 HTTP 401。
    """
    token = os.getenv("DEMO_TOKEN", "").strip()
    if not token:
        return
    if x_demo_token != token:
        raise HTTPException(status_code=401, detail="未授权的访问")
