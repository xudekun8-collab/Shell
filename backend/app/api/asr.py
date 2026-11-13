"""语音识别接口：base64 音频进、文本出；音频只在内存中转。"""
import base64
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.api.deps import require_role
from app.services.asr import AsrError, recognize

logger = logging.getLogger("elder_care")
router = APIRouter()


class AsrRequest(BaseModel):
    audio_base64: str = Field(min_length=1, max_length=4_000_000)
    format: str = "mp3"


class AsrResponse(BaseModel):
    text: str


@router.post("/api/asr", response_model=AsrResponse)
def transcribe(request: AsrRequest, user: dict = Depends(require_role("elder"))) -> AsrResponse:
    if not config.TENCENT_SECRET_ID or not config.TENCENT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="语音识别服务未配置")
    try:
        audio_bytes = base64.b64decode(request.audio_base64.strip(), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="音频数据不合法")
    try:
        text = recognize(audio_bytes, request.format)
    except AsrError as exc:
        logger.warning("ASR 识别失败：%s", exc.code)
        raise HTTPException(status_code=502, detail="这会儿没听清，您再说一遍")
    return AsrResponse(text=text)
