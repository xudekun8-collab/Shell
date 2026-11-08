"""MySQL 集成测试：仅在能连上 MySQL 时执行，连不上自动跳过。"""
import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import database_url


def _mysql_available() -> bool:
    url = database_url()
    if not url.startswith("mysql"):
        return False
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _mysql_available(),
    reason="MySQL 不可用或 DATABASE_URL 未指向 MySQL，跳过集成测试",
)


def test_mysql_schema_and_demo_user():
    engine = create_engine(database_url(), connect_args={"connect_timeout": 3})
    required = {
        "users",
        "profile",
        "conversations",
        "memories",
        "training_records",
        "interaction_events",
    }
    tables = set(inspect(engine).get_table_names())
    assert required <= tables
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT user_id, nickname FROM profile WHERE user_id = :uid"),
            {"uid": "demo_user_1"},
        ).mappings().first()
        assert row is not None
        assert row["nickname"] == "张阿姨"
