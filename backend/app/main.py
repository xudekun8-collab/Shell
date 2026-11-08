"""FastAPI 入口。"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, chat, games, greeting, memory, records
from app.db.session import engine

logger = logging.getLogger("elder_care")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="老年人陪伴与认知活动训练系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(games.router)
app.include_router(greeting.router)
app.include_router(memory.router)
app.include_router(records.router)


@app.get("/api/health")
def health() -> dict:
    """健康检查：顺便探一次数据库连通性。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as exc:  # 数据库文件损坏或被删时不要崩
        logger.warning("健康检查数据库探测失败：%s", exc)
        return {"status": "ok", "db": "degraded"}
