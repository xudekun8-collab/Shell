"""老人画像编辑与家属补充兴趣测试。"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db.init_db import init_db
from app.db.models import FamilyBind, Profile
from app.services.token import create_token

SECRET = "profile-test-secret"


@pytest.fixture()
def client(monkeypatch):
    import app.api.family as family_mod
    import app.api.profile as profile_mod

    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(family_mod, "SessionLocal", factory)
    monkeypatch.setattr(profile_mod, "SessionLocal", factory)
    from app.main import app

    return TestClient(app), factory


def _auth(user_id: str, role: str) -> dict:
    return {"Authorization": "Bearer " + create_token(user_id, role, SECRET)}


def _bind_family(factory):
    with factory() as db:
        db.add(
            FamilyBind(
                elder_id="demo_user_1",
                family_user_id="family_1",
                invite_code="12345678",
                expires_at=datetime.now() + timedelta(days=1),
                bound_at=datetime.now(),
            )
        )
        db.commit()


def test_elder_can_edit_nickname_interests_and_taboos(client):
    c, factory = client
    response = c.put(
        "/api/profile",
        json={
            "nickname": "周先生",
            "interests": ["下棋", "晨走", "下棋"],
            "taboos": ["旧事"],
        },
        headers=_auth("demo_user_1", "elder"),
    )
    assert response.status_code == 200
    assert response.json() == {
        "nickname": "周先生",
        "interests": ["下棋", "晨走"],
        "taboos": ["旧事"],
    }
    with factory() as db:
        profile = db.get(Profile, "demo_user_1")
        assert profile.nickname == "周先生"


def test_elder_nickname_cannot_be_empty(client):
    c, _ = client
    response = c.put(
        "/api/profile",
        json={"nickname": "  "},
        headers=_auth("demo_user_1", "elder"),
    )
    assert response.status_code == 400


def test_family_can_append_interest_but_not_edit_profile(client):
    c, factory = client
    _bind_family(factory)
    headers = _auth("family_1", "family")
    first = c.post(
        "/api/family/interest",
        json={"text": "喜欢散步"},
        headers=headers,
    )
    second = c.post(
        "/api/family/interest",
        json={"text": "喜欢散步"},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["interests"] == ["喜欢散步"]
    assert second.json()["interests"] == ["喜欢散步"]
    assert c.put("/api/profile", json={"nickname": "不能改"}, headers=headers).status_code == 403
