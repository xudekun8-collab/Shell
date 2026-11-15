"""老人端语音合成接口。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app import config
from app.api.deps import require_role
from app.services import tts_tencent

router = APIRouter()
logger = logging.getLogger("elder_care")
CONFIG_ERROR_CODES = {
    "MissingCredential",
    "InvalidVoiceType",
    "UnsupportedOperation.ServerNotOpen",
}


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    speed: float = Field(default=0.0, ge=-1.0, le=1.0)


@router.post("/api/tts")
def synthesize(request: TtsRequest, user: dict = Depends(require_role("elder"))):
    if config.TTS_PROVIDER.strip().lower() == "tencent":
        if not config.TENCENT_SECRET_ID or not config.TENCENT_SECRET_KEY:
            raise HTTPException(status_code=503, detail="语音合成服务未配置")
        try:
            audio = tts_tencent.synthesize(
                request.text,
                voice_type=config.TTS_VOICE or 101001,
                speed=request.speed,
            )
        except tts_tencent.TtsError as exc:
            logger.warning("语音合成失败：%s", exc.code)
            if exc.code in CONFIG_ERROR_CODES or exc.code.startswith(
                ("AuthFailure", "UnauthorizedOperation")
            ):
                raise HTTPException(status_code=503, detail="语音合成服务未配置或未开通") from exc
            raise HTTPException(status_code=502, detail="语音暂时播不出来，先看文字吧") from exc
        return StreamingResponse(iter([audio]), media_type="audio/mpeg")
    if not config.TTS_API_KEY:
        raise HTTPException(status_code=503, detail="语音合成服务未配置")
    raise HTTPException(status_code=501, detail="语音合成尚未接入，见 docs/tts.md")
