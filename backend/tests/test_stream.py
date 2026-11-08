"""流式接口测试：FakeClient 下 SSE 事件与落库行为。"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.agent.rules import SAFETY_TEMPLATES
from app.db.init_db import init_db
from app.db.models import Conversation, Memory
from app.services.token import create_token

SECRET = "test-secret-key-123456"


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data = {}
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :].strip())
        if event is not None:
            events.append({"event": event, "data": data})
    return events


@pytest.fixture()
def stream_client(monkeypatch):
    import app.api.chat as chat_mod
    from app.agent.nodes.act import make_act
    from app.agent.nodes.perceive import make_perceive
    from app.agent.nodes.plan import make_plan
    from app.agent.nodes.retrieve import make_retrieve
    from app.llm.client import FakeClient

    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "DEMO_MODE", "1")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    fake = FakeClient()
    monkeypatch.setattr(chat_mod, "SessionLocal", factory)
    monkeypatch.setattr(chat_mod, "_llm_client", fake)
    monkeypatch.setattr(chat_mod, "_perceive", make_perceive(factory))
    monkeypatch.setattr(chat_mod, "_retrieve", make_retrieve(factory))
    monkeypatch.setattr(chat_mod, "_plan", make_plan(fake, factory))
    monkeypatch.setattr(chat_mod, "_act", make_act(fake, factory))

    from app.main import app

    return TestClient(app), factory


def _headers():
    return {"Authorization": "Bearer " + create_token("demo_user_1", "elder", SECRET)}


def test_stream_meta_delta_done(stream_client):
    client, _ = stream_client
    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "t1", "text": "今天天气不错"},
        headers=_headers(),
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["event"] for e in events]
    assert types[0] == "meta"
    assert types[-1] == "done"
    deltas = "".join(e["data"]["text"] for e in events if e["event"] == "delta")
    assert deltas == "我听着呢，您接着说。"
    assert "latency_first_token_ms" in events[-1]["data"]


def test_medical_single_delta(stream_client):
    client, _ = stream_client
    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "t2", "text": "这药能不能少吃点"},
        headers=_headers(),
    )
    events = _parse_sse(resp.text)
    deltas = [e for e in events if e["event"] == "delta"]
    assert len(deltas) == 1
    assert deltas[0]["data"]["text"] == SAFETY_TEMPLATES["medical"]
    assert events[-1]["event"] == "done"


def test_start_game_no_delta_stream(stream_client):
    client, _ = stream_client
    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "t3", "text": "陪我玩个游戏"},
        headers=_headers(),
    )
    events = _parse_sse(resp.text)
    meta = next(e for e in events if e["event"] == "meta")
    assert meta["data"]["action"] == "start_game"
    deltas = [e for e in events if e["event"] == "delta"]
    assert len(deltas) == 1


def test_stream_persists_conversation_and_memory(stream_client):
    client, factory = stream_client
    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "t4", "text": "我孙女上周来看我了"},
        headers=_headers(),
    )
    assert resp.status_code == 200
    with factory() as db:
        conv = db.get(Conversation, "t4")
        assert conv is not None
        assert conv.msg_count == 1
        events = db.execute(
            select(Memory).where(Memory.user_id == "demo_user_1", Memory.layer == "event")
        ).scalars().all()
        assert len(events) >= 1
