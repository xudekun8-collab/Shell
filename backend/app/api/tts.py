"""语音合成接口：本轮只搭骨架，不接真实云 TTS。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.api.deps import current_user

router = APIRouter()


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


@router.post("/api/tts")
def synthesize(request: TtsRequest, user: dict = Depends(current_user)):
    # 接入点：待接入云 TTS 后，用 TTS_API_KEY/TTS_VOICE/TTS_PROVIDER 调云服务拿 mp3 字节流，
    # 返回 StreamingResponse(content=bytes, media_type="audio/mpeg")。不打印 key 与 text 原文。
    if not config.TTS_API_KEY:
        raise HTTPException(status_code=503, detail="语音合成服务未配置")
    raise HTTPException(status_code=501, detail="语音合成尚未接入，见 docs/tts.md")
