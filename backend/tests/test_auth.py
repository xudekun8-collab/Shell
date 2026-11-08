"""身份认证测试：token 签发、401/403、微信登录与演示登录。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db.init_db import init_db
from app.db.models import Memory, Profile, User
from app.services.token import create_token, decode_token

SECRET = "test-secret-key-123456"


@pytest.fixture()
def auth_env(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "DEMO_MODE", "0")
    monkeypatch.setattr(config, "WX_APPID", "")
    monkeypatch.setattr(config, "WX_SECRET", "")


@pytest.fixture()
def client(auth_env):
    from app.main import app

    return TestClient(app)


def _headers(token):
    return {"Authorization": "Bearer " + token}


def _memory_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_no_token_all_endpoints_401(client):
    cases = [
        ("POST", "/api/chat", {"thread_id": "t1", "text": "你好"}),
        ("POST", "/api/game/start", {"game_type": "memory_box"}),
        ("POST", "/api/game/submit", {"session_id": "x", "answers": []}),
        ("GET", "/api/records", None),
        ("GET", "/api/memories", None),
        ("GET", "/api/greeting", None),
    ]
    for method, path, body in cases:
        resp = client.request(method, path, json=body)
        assert resp.status_code == 401, path


def test_records_with_token_200(client, monkeypatch):
    import app.api.records as records_mod

    factory = _memory_factory()
    monkeypatch.setattr(records_mod, "SessionLocal", factory)
    token = create_token("demo_user_1", "elder", SECRET)
    resp = client.get("/api/records", headers=_headers(token))
    assert resp.status_code == 200


def test_legacy_path_403_when_demo_mode_off(client):
    # DEMO_MODE=0（auth_env 默认）时旧版带 user_id 的路径被拒绝
    resp = client.get("/api/records/demo_user_1")
    assert resp.status_code == 403


def test_delete_other_user_memory_403(client, monkeypatch):
    import app.api.memory as memory_mod

    factory = _memory_factory()
    monkeypatch.setattr(memory_mod, "SessionLocal", factory)
    with factory() as db:
        m = Memory(user_id="user_b", layer="event", content="B 的记忆", importance=3)
        db.add(m)
        db.commit()
        memory_id = m.id
    token_a = create_token("user_a", "elder", SECRET)
    resp = client.delete(f"/api/memories/{memory_id}", headers=_headers(token_a))
    assert resp.status_code == 403


def test_demo_login_disabled_401(client):
    resp = client.post("/api/auth/demo", json={"user_id": "demo_user_1"})
    assert resp.status_code == 401


def test_expired_token_401(client):
    token = create_token("u1", "elder", SECRET, ttl_seconds=-10)
    resp = client.get("/api/records", headers=_headers(token))
    assert resp.status_code == 401


def test_tampered_token_401(client):
    token = create_token("u1", "elder", SECRET)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    resp = client.get("/api/records", headers=_headers(tampered))
    assert resp.status_code == 401


def test_family_token_carries_role():
    token = create_token("fam_1", "family", SECRET)
    payload = decode_token(token, SECRET)
    assert payload["role"] == "family"
    assert payload["user_id"] == "fam_1"


def test_wx_login_creates_profile_once(client, monkeypatch):
    import app.api.auth as auth_mod

    monkeypatch.setattr(config, "WX_APPID", "appid")
    monkeypatch.setattr(config, "WX_SECRET", "secret")
    factory = _memory_factory()
    monkeypatch.setattr(auth_mod, "SessionLocal", factory)

    class FakeResp:
        def json(self):
            return {"openid": "abc1234567890xyz"}

    monkeypatch.setattr(auth_mod.httpx, "get", lambda url, params=None, timeout=None: FakeResp())

    r1 = client.post("/api/auth/wx", json={"code": "c1"})
    assert r1.status_code == 200
    user_id = r1.json()["user_id"]
    assert user_id.startswith("wx_")
    r2 = client.post("/api/auth/wx", json={"code": "c2"})
    assert r2.status_code == 200
    assert r2.json()["user_id"] == user_id
    with factory() as db:
        assert db.get(User, user_id) is not None
        profile = db.get(Profile, user_id)
        assert profile is not None
        assert profile.nickname == "您好"


def test_demo_login_works_when_enabled(client, monkeypatch):
    import app.api.auth as auth_mod

    monkeypatch.setattr(config, "DEMO_MODE", "1")
    factory = _memory_factory()
    monkeypatch.setattr(auth_mod, "SessionLocal", factory)
    resp = client.post("/api/auth/demo", json={"user_id": "demo_user_1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["role"] == "elder"
    assert body["user_id"] == "demo_user_1"
