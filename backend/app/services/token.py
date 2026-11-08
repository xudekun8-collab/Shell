"""JWT HS256 的极简实现：只依赖标准库，离线可跑。"""
import base64
import hashlib
import hmac
import json
import time


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(user_id: str, role: str, secret: str, ttl_seconds: int = 7 * 24 * 3600) -> str:
    """签发 HS256 JWT，默认 7 天过期。"""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"user_id": user_id, "role": role, "exp": int(time.time()) + ttl_seconds}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing = (h + "." + p).encode("ascii")
    sig = _b64url(hmac.new(secret.encode("utf-8"), signing, hashlib.sha256).digest())
    return h + "." + p + "." + sig


def decode_token(token: str, secret: str) -> dict:
    """校验签名与过期，返回 payload；任何不合法都抛 ValueError。"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("token 格式错误")
    h, p, sig = parts
    signing = (h + "." + p).encode("ascii")
    expected = _b64url(hmac.new(secret.encode("utf-8"), signing, hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise ValueError("签名错误")
    payload = json.loads(_unb64url(p))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("token 已过期")
    return payload
