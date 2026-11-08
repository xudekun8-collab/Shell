# 确保 backend 目录在 sys.path 中，便于 tests 导入 app 包
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db


@pytest.fixture()
def factory():
    """SQLite 内存库的 sessionmaker，建好全部表。"""
    engine = create_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

