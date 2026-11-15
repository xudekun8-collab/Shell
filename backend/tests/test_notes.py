"""家属留言与老人读取接口测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db.init_db import init_db
from app.services.token import create_token

SECRET = "notes-test-secret"


@pytest.fixture()
def client(monkeypatch):
    import app.api.family as family_mod
    import app.api.notes as notes_mod

    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(family_mod, "SessionLocal", factory)
    monkeypatch.setattr(notes_mod, "SessionLocal", factory)
    from app.main import app

    return TestClient(app)


def _auth(user_id: str, role: str) -> dict:
    return {"Authorization": "Bearer " + create_token(user_id, role, SECRET)}


def _family_headers(c: TestClient) -> dict:
    invite = c.post("/api/family/invite", headers=_auth("elder_1", "elder"))
    assert invite.status_code == 200
    bound = c.post("/api/family/bind", json={"invite_code": invite.json()["invite_code"]})
    assert bound.status_code == 200
    return {"Authorization": "Bearer " + bound.json()["token"]}


def test_family_note_can_be_read_once(client):
    family_headers = _family_headers(client)
    created = client.post(
        "/api/family/note",
        json={"text": "  晚上记得喝温水  "},
        headers=family_headers,
    )
    assert created.status_code == 200
    assert created.json()["text"] == "晚上记得喝温水"
    note_id = created.json()["id"]

    elder_headers = _auth("elder_1", "elder")
    unread = client.get("/api/notes", headers=elder_headers)
    assert unread.status_code == 200
    assert unread.json() == {
        "unread_count": 1,
        "note": {"id": note_id, "text": "晚上记得喝温水"},
    }

    assert client.post(f"/api/notes/{note_id}/read", headers=elder_headers).status_code == 200
    assert client.post(f"/api/notes/{note_id}/read", headers=elder_headers).json() == {"read": True}
    assert client.get("/api/notes", headers=elder_headers).json() == {
        "unread_count": 0,
        "note": None,
    }

    listed = client.get("/api/family/notes", headers=family_headers)
    assert listed.status_code == 200
    assert listed.json()["notes"][0]["read"] is True


def test_family_note_length_and_daily_limit(client):
    family_headers = _family_headers(client)
    too_long = client.post(
        "/api/family/note",
        json={"text": "话" * 61},
        headers=family_headers,
    )
    assert too_long.status_code == 400
    assert too_long.json()["detail"] == "话太长了，短一点"

    for index in range(3):
        response = client.post(
            "/api/family/note",
            json={"text": f"第 {index + 1} 句"},
            headers=family_headers,
        )
        assert response.status_code == 200
    fourth = client.post(
        "/api/family/note",
        json={"text": "第 4 句"},
        headers=family_headers,
    )
    assert fourth.status_code == 429
    assert fourth.json()["detail"] == "今天已经留过话了"


def test_other_elder_cannot_read_note(client):
    family_headers = _family_headers(client)
    note_id = client.post(
        "/api/family/note",
        json={"text": "给老人"},
        headers=family_headers,
    ).json()["id"]
    response = client.post(
        f"/api/notes/{note_id}/read",
        headers=_auth("elder_2", "elder"),
    )
    assert response.status_code == 404
