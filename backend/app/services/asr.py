"""腾讯云一句话识别：TC3-HMAC-SHA256 直连，只用标准库 + httpx，无 SDK。"""
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from app import config

logger = logging.getLogger("elder_care")

HOST = "asr.tencentcloudapi.com"
SERVICE = "asr"
ACTION = "SentenceRecognition"
VERSION = "2019-06-14"
ALGORITHM = "TC3-HMAC-SHA256"
CONTENT_TYPE = "application/json; charset=utf-8"


class AsrError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def recognize(audio_bytes: bytes, voice_format: str = "mp3") -> str:
    """调用腾讯云一句话识别，返回识别文本；失败抛 AsrError（只带 Code，不带密钥）。"""
    if not config.TENCENT_SECRET_ID or not config.TENCENT_SECRET_KEY:
        raise AsrError("MissingCredential", "未配置腾讯云密钥")

    payload = {
        "EngSerViceType": "16k_zh",
        "SourceType": 1,
        "VoiceFormat": voice_format,
        "Data": base64.b64encode(audio_bytes).decode("ascii"),
        "DataLen": len(audio_bytes),
        "ProjectId": 0,
        "SubServiceType": 2,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    now = datetime.now(timezone.utc)
    timestamp = int(now.timestamp())
    date = now.strftime("%Y-%m-%d")

    canonical_headers = f"content-type:{CONTENT_TYPE}\nhost:{HOST}\n"
    signed_headers = "content-type;host"
    canonical_request = (
        "POST\n/\n\n"
        + canonical_headers
        + "\n"
        + signed_headers
        + "\n"
        + _sha256_hex(payload_bytes)
    )
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = (
        f"{ALGORITHM}\n{timestamp}\n{credential_scope}\n"
        + _sha256_hex(canonical_request.encode("utf-8"))
    )

    secret_date = _hmac(("TC3" + config.TENCENT_SECRET_KEY).encode("utf-8"), date)
    secret_service = _hmac(secret_date, SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers = {
        "Authorization": (
            f"{ALGORITHM} Credential={config.TENCENT_SECRET_ID}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": CONTENT_TYPE,
        "Host": HOST,
        "X-TC-Action": ACTION,
        "X-TC-Version": VERSION,
        "X-TC-Region": config.TENCENT_ASR_REGION,
        "X-TC-Timestamp": str(timestamp),
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"https://{HOST}", headers=headers, content=payload_bytes)
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("腾讯云 ASR 请求失败：%s", type(exc).__name__)
        raise AsrError("RequestFailed") from exc
    if not isinstance(body, dict):
        logger.warning("腾讯云 ASR 响应格式错误：%s", type(body).__name__)
        raise AsrError("InvalidResponse")
    response = body.get("Response") or {}
    error = response.get("Error")
    if error:
        logger.warning("腾讯云 ASR 返回错误：%s", error.get("Code"))
        raise AsrError(error.get("Code", "Unknown"), error.get("Message", ""))
    return str(response.get("Result") or "").strip()
