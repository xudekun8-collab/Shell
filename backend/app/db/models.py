"""数据库表模型：6 张核心表，字段名与类型严格按约定。"""
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.mysql import TINYINT as MySQLTINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# MySQL 下渲染为 TINYINT，SQLite 测试下退化为 SMALLINT
TinyInt = SmallInteger().with_variant(MySQLTINYINT(), "mysql")

# SQLite 里只有 INTEGER PRIMARY KEY 才是 rowid 别名，
# 用 BIGINT 建主键不会自增（插入会得到 NULL 主键且不报错），因此按方言退化。
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )


class Profile(Base):
    __tablename__ = "profile"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(32), nullable=False)
    interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    taboos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    wake_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(7, 0), server_default="07:00:00"
    )
    sleep_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(22, 0), server_default="22:00:00"
    )
    consent_reminder: Mapped[int] = mapped_column(
        TinyInt, nullable=False, default=0, server_default="0"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 即 thread_id
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    msg_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        onupdate=datetime.now,
    )


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(16), nullable=False)  # event / session
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(
        TinyInt, nullable=False, default=3, server_default="3"
    )
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[int] = mapped_column(
        TinyInt, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        onupdate=datetime.now,
    )


class TrainingRecord(Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[int] = mapped_column(TinyInt, nullable=False)
    correct_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    duration_sec: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    abandoned: Mapped[int] = mapped_column(
        TinyInt, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )


class InteractionEvent(Base):
    __tablename__ = "interaction_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    perceived: Mapped[dict] = mapped_column(JSON, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
