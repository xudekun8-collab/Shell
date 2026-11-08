"""从 .env 读取数据库与大模型配置。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/ 目录，用于把相对的 SQLite 路径固定解析到项目内，
# 避免从不同工作目录启动服务时生成两个库文件。
BASE_DIR = Path(__file__).resolve().parent.parent

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

WX_APPID = os.getenv("WX_APPID", "")
WX_SECRET = os.getenv("WX_SECRET", "")
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
DEMO_MODE = os.getenv("DEMO_MODE", "0")


def database_url() -> str:
    """返回 SQLAlchemy 连接串。

    缺省用 backend/elder_care.db；若 DATABASE_URL 里给的是相对 SQLite 路径，
    统一按 backend 目录解析。将来换成 mysql+pymysql://... 时原样返回。
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{(BASE_DIR / 'elder_care.db').as_posix()}"

    prefix = "sqlite:///"
    if url.startswith(prefix):
        raw = url[len(prefix) :]
        path = Path(raw)
        if not path.is_absolute():
            path = (BASE_DIR / raw).resolve()
        return f"sqlite:///{path.as_posix()}"

    return url
