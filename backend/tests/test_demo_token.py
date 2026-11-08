"""请求头校验依赖的开关测试（内存 SQLite，不连 MySQL）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.records as records_mod
from app.db.init_db import init_db


@pytest.fixture()
def client(monkeypatch):
    """用共享单连接的内存 SQLite 替换 records 的会话工厂，走 TestClient。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(records_mod, "SessionLocal", factory)
    from app.main import app

    return TestClient(app)


def test_no_token_keeps_200(client, monkeypatch):
    """未设置 DEMO_TOKEN：照常 200，现状不变。"""
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    resp = client.get("/api/records/demo_user_1")
    assert resp.status_code == 200


def test_token_set_without_header_401(client, monkeypatch):
    """设置 DEMO_TOKEN 后不带请求头：401。"""
    monkeypatch.setenv("DEMO_TOKEN", "abc123")
    resp = client.get("/api/records/demo_user_1")
    assert resp.status_code == 401


def test_token_set_with_correct_header_200(client, monkeypatch):
    """设置后带正确请求头：200。"""
    monkeypatch.setenv("DEMO_TOKEN", "abc123")
    resp = client.get("/api/records/demo_user_1", headers={"X-Demo-Token": "abc123"})
    assert resp.status_code == 200
