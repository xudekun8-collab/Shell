"""冒烟测试：SQLite 建表、演示用户、自增主键、TIME 转换。"""
from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.db.models import Memory, Profile, User
from app.db.session import to_time


def test_smoke():
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as session:
        user = session.get(User, "demo_user_1")
        assert user is not None
        profile = session.get(Profile, "demo_user_1")
        assert profile is not None
        assert profile.nickname == "张阿姨"
        assert profile.interests == ["黄梅戏", "养花"]
        assert profile.taboos == ["不要提去世的老伴"]
        # SQLite 下 TIME 取出来是字符串，必须能通过 to_time 还原
        assert to_time(profile.wake_time) == time(7, 0)
        assert to_time(profile.sleep_time) == time(22, 0)


def test_autoincrement_pk_on_sqlite():
    """BIGINT 主键在 SQLite 下不会自增，这里守住这个坑。"""
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as session:
        row = Memory(
            user_id="demo_user_1",
            layer="event",
            content="孙女上周末来看我",
            importance=4,
            occurred_at=date(2026, 11, 1),
        )
        session.add(row)
        session.commit()
        assert row.id is not None
        assert row.id == 1
