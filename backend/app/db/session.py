"""数据库引擎、会话工厂与类型转换工具。"""
from datetime import time
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import database_url

engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    # SQLite 在多线程下需要关闭同线程检查（FastAPI 会用到线程池）
    connect_args={"check_same_thread": False} if database_url().startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def to_time(value: Any) -> time:
    """把数据库里取出的 TIME 值统一成 datetime.time。

    SQLite 返回字符串（如 "07:00:00"）或 None，MySQL 返回 datetime.time。
    所有涉及作息的判断都必须走这个函数，禁止直接比较字符串。
    """
    if isinstance(value, time):
        return value
    if value is None:
        return time(0, 0)
    if isinstance(value, str):
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(float(parts[2])) if len(parts) > 2 else 0
        return time(hour, minute, second)
    raise TypeError(f"无法识别的 TIME 值: {value!r}")
