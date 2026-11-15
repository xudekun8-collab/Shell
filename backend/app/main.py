"""FastAPI 入口。"""
import logging
import time

from fastapi import FastAPI
from sqlalchemy import text

from app import config
from app.api import asr, auth, chat, family, games, greeting, memory, notes, profile, records, tts
from app.db.session import engine

logger = logging.getLogger("elder_care")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_PROCESS_STARTED_AT = time.time()
SLOW_REQUEST_MS = 2000.0

app = FastAPI(title="老年人陪伴与认知活动训练系统")

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(games.router)
app.include_router(greeting.router)
app.include_router(memory.router)
app.include_router(profile.router)
app.include_router(records.router)
app.include_router(tts.router)
app.include_router(family.router)
app.include_router(notes.router)
app.include_router(asr.router)


def _log_request(method: str, path: str, status_code: int, elapsed_ms: float) -> None:
    try:
        message = f"{method} {path} {status_code} {elapsed_ms:.1f}ms"
        if elapsed_ms > SLOW_REQUEST_MS:
            logger.warning("SLOW %s", message)
        else:
            logger.info("%s", message)
    except Exception:
        pass


@app.middleware("http")
async def log_request(request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        raise
    finally:
        try:
            elapsed_ms = (time.perf_counter() - started) * 1000
            _log_request(request.method, request.url.path, status_code, elapsed_ms)
        except Exception:
            pass


@app.get("/api/health")
def health() -> dict:
    """健康检查：顺便探一次数据库连通性。"""
    tts_provider = (config.TTS_PROVIDER or "").strip().lower()
    payload = {
        "status": "ok",
        "db": "ok",
        "uptime_sec": round(max(0.0, time.time() - _PROCESS_STARTED_AT), 3),
        "asr_configured": bool(config.TENCENT_SECRET_ID and config.TENCENT_SECRET_KEY),
        "tts_configured": bool(
            (
                tts_provider == "tencent"
                and config.TENCENT_SECRET_ID
                and config.TENCENT_SECRET_KEY
            )
            or config.TTS_API_KEY
        ),
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return payload
    except Exception as exc:  # 数据库文件损坏或被删时不要崩
        logger.warning("健康检查数据库探测失败：%s", exc)
        payload["db"] = "degraded"
        return payload
