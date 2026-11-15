"""家属端测试：邀请码绑定、只读三接口、写操作 403、过期与未绑定。"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db.init_db import init_db
from app.db.models import BindAttempt, FamilyBind
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


def _bind(c):
    invite = c.post("/api/family/invite", headers=_elder_headers())
    assert invite.status_code == 200
    code = invite.json()["invite_code"]
    resp = c.post("/api/family/bind", json={"invite_code": code})
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
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "邀请码无效或已用过"


def test_unbound_family_404(client):
    c, _ = client
    headers = {"Authorization": "Bearer " + create_token("family_9", "family", SECRET)}
    for path in ("/api/family/overview", "/api/family/records", "/api/family/alerts"):
        resp = c.get(path, headers=headers)
        assert resp.status_code == 404, path


def test_public_bind_without_authorization_200(client):
    c, _ = client
    invite = c.post("/api/family/invite", headers=_elder_headers())
    assert invite.status_code == 200
    code = invite.json()["invite_code"]
    resp = c.post("/api/family/bind", json={"invite_code": code})
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_family_invite_403(client):
    c, _ = client
    headers = {"Authorization": "Bearer " + create_token("family_x", "family", SECRET)}
    resp = c.post("/api/family/invite", headers=headers)
    assert resp.status_code == 403


def test_public_bind_invalid_code_400(client):
    c, _ = client
    resp = c.post("/api/family/bind", json={"invite_code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "邀请码无效或已用过"


def test_invite_is_8_digits_and_limited_to_three_per_24_hours(client):
    c, _ = client
    responses = [
        c.post("/api/family/invite", headers=_elder_headers())
        for _ in range(10)
    ]
    first_codes = [response.json()["invite_code"] for response in responses[:3]]
    assert all(response.status_code == 200 for response in responses[:3])
    assert all(len(code) == 8 and code.isdigit() for code in first_codes)
    assert len(set(first_codes)) == 3
    for response in responses[3:]:
        assert response.status_code == 429
        assert response.json()["detail"] == "今天已经发过好几次了，让家人用最早那个"


def test_invite_generation_stops_after_five_code_conflicts(client, monkeypatch):
    c, factory = client
    import app.api.family as family_mod

    with factory() as db:
        for index in range(5):
            db.add(
                FamilyBind(
                    elder_id=f"other_{index}",
                    invite_code="00000001",
                    expires_at=datetime.now() + timedelta(hours=1),
                )
            )
        db.commit()

    calls = []

    def always_conflict(_):
        calls.append(1)
        return 1

    monkeypatch.setattr(family_mod.secrets, "randbelow", always_conflict)
    resp = c.post("/api/family/invite", headers=_elder_headers())
    assert resp.status_code == 500
    assert resp.json()["detail"] == "邀请码生成失败，请再试一次"
    assert len(calls) == 5


def test_bind_sixth_failure_429(client):
    c, _ = client
    for attempt in range(5):
        response = c.post(
            "/api/family/bind",
            json={"invite_code": f"bad-{attempt}"},
        )
        assert response.status_code == 400
    sixth = c.post(
        "/api/family/bind",
        json={"invite_code": "bad-5"},
    )
    assert sixth.status_code == 429
    assert sixth.json()["detail"] == "试的次数太多了，过一会再试"


def test_bind_limit_can_use_trusted_proxy_client_ip(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", True)
    for attempt in range(5):
        response = c.post(
            "/api/family/bind",
            json={"invite_code": f"bad-proxy-{attempt}"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        assert response.status_code == 400
    limited = c.post(
        "/api/family/bind",
        json={"invite_code": "bad-proxy-final"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    other_ip = c.post(
        "/api/family/bind",
        json={"invite_code": "bad-other-ip"},
        headers={"X-Forwarded-For": "203.0.113.11"},
    )
    assert limited.status_code == 429
    assert other_ip.status_code == 400


def test_successful_bind_clears_failure_count(client):
    c, factory = client
    invite = c.post("/api/family/invite", headers=_elder_headers())
    code = invite.json()["invite_code"]
    for attempt in range(3):
        c.post(
            "/api/family/bind",
            json={"invite_code": f"bad-{attempt}"},
        )
    success = c.post(
        "/api/family/bind",
        json={"invite_code": code},
    )
    assert success.status_code == 200
    with factory() as db:
        attempt = db.execute(select(BindAttempt)).scalars().one()
        assert attempt.user_id.startswith("ip:")
        assert attempt is not None
        assert attempt.fail_count == 0


def test_invite_is_one_time(client):
    c, _ = client
    invite = c.post("/api/family/invite", headers=_elder_headers())
    code = invite.json()["invite_code"]
    first = c.post(
        "/api/family/bind",
        json={"invite_code": code},
    )
    assert first.status_code == 200
    second = c.post(
        "/api/family/bind",
        json={"invite_code": code},
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "邀请码无效或已用过"
