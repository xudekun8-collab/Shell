"""家属端测试：邀请码绑定、只读三接口、写操作 403、过期与未绑定。"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db.init_db import init_db
from app.db.models import FamilyBind
from app.services.token import create_token

SECRET = "family-test-secret"


@pytest.fixture()
def client(monkeypatch):
    import app.api.family as family_mod

    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(family_mod, "SessionLocal", factory)
    from app.main import app

    return TestClient(app), factory


def _elder_headers():
    return {"Authorization": "Bearer " + create_token("elder_1", "elder", SECRET)}


def _pre_bind_family_headers():
    # 家属先用微信登录（初始 role=elder），绑定后换发 role=family
    return {"Authorization": "Bearer " + create_token("family_1", "elder", SECRET)}


def _bind(c):
    invite = c.post("/api/family/invite", headers=_elder_headers())
    assert invite.status_code == 200
    code = invite.json()["invite_code"]
    resp = c.post("/api/family/bind", json={"invite_code": code}, headers=_pre_bind_family_headers())
    assert resp.status_code == 200
    return resp.json()["token"]


def test_family_read_three_endpoints_200(client):
    c, _ = client
    token = _bind(c)
    headers = {"Authorization": "Bearer " + token}
    for path in ("/api/family/overview", "/api/family/records", "/api/family/alerts"):
        resp = c.get(path, headers=headers)
        assert resp.status_code == 200, path


def test_family_write_operations_403(client):
    c, _ = client
    token = _bind(c)
    headers = {"Authorization": "Bearer " + token}
    assert c.post("/api/chat", json={"thread_id": "t", "text": "你好"}, headers=headers).status_code == 403
    assert c.delete("/api/memories/1", headers=headers).status_code == 403
    assert c.post("/api/game/start", json={"game_type": "memory_box"}, headers=headers).status_code == 403


def test_invite_code_expired(client):
    c, factory = client
    with factory() as db:
        db.add(
            FamilyBind(
                elder_id="elder_1",
                invite_code="123456",
                expires_at=datetime.now() - timedelta(hours=1),
            )
        )
        db.commit()
    resp = c.post(
        "/api/family/bind",
        json={"invite_code": "123456"},
        headers=_pre_bind_family_headers(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "邀请码无效或已过期"


def test_unbound_family_404(client):
    c, _ = client
    headers = {"Authorization": "Bearer " + create_token("family_9", "family", SECRET)}
    for path in ("/api/family/overview", "/api/family/records", "/api/family/alerts"):
        resp = c.get(path, headers=headers)
        assert resp.status_code == 404, path


def test_self_bind_400(client):
    c, _ = client
    invite = c.post("/api/family/invite", headers=_elder_headers())
    assert invite.status_code == 200
    code = invite.json()["invite_code"]
    resp = c.post("/api/family/bind", json={"invite_code": code}, headers=_elder_headers())
    assert resp.status_code == 400
    assert resp.json()["detail"] == "不能绑定自己的邀请码"


def test_family_invite_403(client):
    c, _ = client
    headers = {"Authorization": "Bearer " + create_token("family_x", "family", SECRET)}
    resp = c.post("/api/family/invite", headers=headers)
    assert resp.status_code == 403


def test_family_bind_again_400(client):
    c, _ = client
    token = _bind(c)
    resp = c.post(
        "/api/family/bind",
        json={"invite_code": "000000"},
        headers={"Authorization": "Bearer " + token},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "家属账号无需再绑定"
