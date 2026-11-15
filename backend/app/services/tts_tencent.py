"""腾讯云语音合成：TC3-HMAC-SHA256 直连，只使用标准库。"""
import base64
import binascii
import hashlib
import hmac
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import request as urlrequest

from app import config

logger = logging.getLogger("elder_care")

HOST = "tts.tencentcloudapi.com"
SERVICE = "tts"
ACTION = "TextToVoice"
VERSION = "2019-08-23"
ALGORITHM = "TC3-HMAC-SHA256"
CONTENT_TYPE = "application/json; charset=utf-8"
MAX_TEXT_CHARS = 120
CACHE_LIMIT = 200

_CACHE: dict[str, bytes] = {}
_CACHE_LOCK = threading.Lock()


class TtsError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _headers(payload_bytes: bytes) -> dict[str, str]:
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
        secret_signing,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
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


def _post_json(payload_bytes: bytes, headers: dict[str, str]) -> dict:
    req = urlrequest.Request(
        f"https://{HOST}",
        data=payload_bytes,
        headers=headers,
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urlerror.URLError, TimeoutError, ValueError) as exc:
        logger.warning("腾讯云 TTS 请求失败：%s", type(exc).__name__)
        raise TtsError("RequestFailed") from exc
    if not isinstance(body, dict):
        logger.warning("腾讯云 TTS 响应格式错误：%s", type(body).__name__)
        raise TtsError("InvalidResponse")
    return body


def _cache_key(text: str, voice_type: int, speed: float) -> str:
    source = f"{text}\0{voice_type}\0{speed:.3f}".encode("utf-8")
    return hashlib.sha256(source).hexdigest()


def _remember(key: str, audio: bytes) -> None:
    with _CACHE_LOCK:
        _CACHE.pop(key, None)
        while len(_CACHE) >= CACHE_LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = audio


def synthesize(text: str, voice_type: int | None = None, speed: float = 0.0) -> bytes:
    """合成最多 120 字的 MP3；日志只记录上游错误码和消息。"""
    if not config.TENCENT_SECRET_ID or not config.TENCENT_SECRET_KEY:
        raise TtsError("MissingCredential", "未配置腾讯云密钥")
    safe_text = (text or "")[:MAX_TEXT_CHARS]
    if not safe_text:
        raise TtsError("EmptyText")
    try:
        resolved_voice = int(voice_type or config.TTS_VOICE or 101001)
    except (TypeError, ValueError) as exc:
        raise TtsError("InvalidVoiceType") from exc
    resolved_speed = max(-1.0, min(1.0, float(speed)))
    key = _cache_key(safe_text, resolved_voice, resolved_speed)
    with _CACHE_LOCK:
        cached = _CACHE.pop(key, None)
        if cached is not None:
            _CACHE[key] = cached
    if cached is not None:
        return cached

    payload = {
        "Text": safe_text,
        "SessionId": uuid.uuid4().hex,
        "VoiceType": resolved_voice,
        "Codec": "mp3",
        "SampleRate": 16000,
        "Speed": resolved_speed,
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    body = _post_json(payload_bytes, _headers(payload_bytes))
    response = body.get("Response") or {}
    error = response.get("Error")
    if error:
        code = str(error.get("Code") or "Unknown")
        message = str(error.get("Message") or "")
        logger.warning("腾讯云 TTS 返回错误：%s %s", code, message)
        raise TtsError(code, message)
    try:
        audio = base64.b64decode(response.get("Audio") or "", validate=True)
    except (binascii.Error, ValueError) as exc:
        logger.warning("腾讯云 TTS 音频数据不合法")
        raise TtsError("InvalidAudio") from exc
    if not audio:
        logger.warning("腾讯云 TTS 返回空音频")
        raise TtsError("InvalidAudio")
    _remember(key, audio)
    return audio
