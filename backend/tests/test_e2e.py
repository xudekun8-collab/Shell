"""接口级端到端测试：一条主链 + 若干反向用例，全部走内存 SQLite + FakeClient。"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.agent.rules import SAFETY_TEMPLATES
from app.db.init_db import init_db
from app.db.models import Memory
from app.services.token import create_token

SECRET = "e2e-test-secret"


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
def e2e(monkeypatch):
    import app.agent.context as context_mod
    import app.api.auth as auth_mod
    import app.api.chat as chat_mod
    import app.api.games as games_mod
    import app.api.greeting as greeting_mod
    import app.api.memory as memory_mod
    import app.api.records as records_mod
    from app.agent.graph import build_graph
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

    for mod in (chat_mod, records_mod, memory_mod, games_mod, greeting_mod, auth_mod, context_mod):
        monkeypatch.setattr(mod, "SessionLocal", factory)

    fake = FakeClient()
    monkeypatch.setattr(chat_mod, "_llm_client", fake)
    monkeypatch.setattr(chat_mod, "_perceive", make_perceive(factory))
    monkeypatch.setattr(chat_mod, "_retrieve", make_retrieve(factory))
    monkeypatch.setattr(chat_mod, "_plan", make_plan(fake, factory))
    monkeypatch.setattr(chat_mod, "_act", make_act(fake, factory))
    monkeypatch.setattr(chat_mod, "_graph", build_graph(fake, factory))

    from app.main import app

    return TestClient(app), factory


def _auth(token):
    return {"Authorization": "Bearer " + token}


def test_full_chain(e2e):
    client, factory = e2e
    token = create_token("demo_user_1", "elder", SECRET)
    headers = _auth(token)

    # a) 问候
    g = client.get("/api/greeting?thread_id=e2e", headers=headers)
    assert g.status_code == 200
    assert g.json()["greeting"]
    assert g.json()["period"] in {"morning", "noon", "afternoon", "evening", "night"}

    # b) 普通闲聊（"昨天" 触发事件记忆，供后面 h/i 使用）
    r = client.post("/api/chat", json={"thread_id": "e2e", "text": "昨天有点闷"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["action"] == "reply"
    assert r.json()["reply_text"]

    # c) 医疗安全规则：决策层拦截
    r = client.post("/api/chat", json={"thread_id": "e2e", "text": "这药能不能少吃点"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["reply_text"] == SAFETY_TEMPLATES["medical"]

    # d) 启动游戏
    r = client.post("/api/chat", json={"thread_id": "e2e", "text": "陪我玩个游戏"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["action"] == "start_game"
    assert "game_type" in (r.json()["params"] or {})

    # e) 开始一局
    start = client.post("/api/game/start", json={"game_type": "memory_box"}, headers=headers)
    assert start.status_code == 200
    s = start.json()
    assert s["session_id"]
    assert 1 <= s["difficulty"] <= 3
    assert s["items"]
    quizzes = s["items"]["quizzes"]

    # f) 提交成绩（全对）
    answers = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes)]
    sub = client.post(
        "/api/game/submit",
        json={"session_id": s["session_id"], "answers": answers, "duration_sec": 20},
        headers=headers,
    )
    assert sub.status_code == 200
    assert sub.json()["total"] > 0
    assert sub.json()["accuracy"] >= 0
    assert "这次完成了" in sub.json()["summary_text"]

    # g) 记录
    rec = client.get("/api/records", headers=headers)
    assert rec.status_code == 200
    rj = rec.json()
    assert rj["records"][0]["game_type"] == "memory_box"
    assert rj["records"][0]["total_count"] > 0
    assert rj["summary"]["total"] >= 1
    assert any(b["game_type"] == "memory_box" for b in rj["summary"]["by_type"])

    # h) 记忆
    mem = client.get("/api/memories", headers=headers)
    assert mem.status_code == 200
    events = mem.json()["events"]
    assert len(events) >= 1

    # i) 删除记忆
    mid = events[0]["memory_id"]
    d = client.delete(f"/api/memories/{mid}", headers=headers)
    assert d.status_code == 200
    assert d.json()["deleted"] is True
    mem2 = client.get("/api/memories", headers=headers)
    assert mid not in [e["memory_id"] for e in mem2.json()["events"]]


def test_no_token_401(e2e):
    client, _ = e2e
    assert client.post("/api/chat", json={"thread_id": "t", "text": "hi"}).status_code == 401
    assert client.get("/api/records").status_code == 401
    assert client.post("/api/game/start", json={"game_type": "memory_box"}).status_code == 401


def test_legacy_path_blocked(e2e, monkeypatch):
    client, _ = e2e
    monkeypatch.setattr(config, "DEMO_MODE", "0")
    token = create_token("demo_user_1", "elder", SECRET)
    resp = client.get("/api/records/demo_user_1", headers=_auth(token))
    assert resp.status_code == 403


def test_stream_and_chat_same_result(e2e):
    client, _ = e2e
    token = create_token("demo_user_1", "elder", SECRET)
    headers = _auth(token)
    text = "今天天气不错"
    non_stream = client.post("/api/chat", json={"thread_id": "t_ns", "text": text}, headers=headers)
    stream = client.post("/api/chat/stream", json={"thread_id": "t_s", "text": text}, headers=headers)
    assert non_stream.status_code == 200
    assert stream.status_code == 200
    events = _parse_sse(stream.text)
    meta = next(e for e in events if e["event"] == "meta")
    deltas = "".join(e["data"]["text"] for e in events if e["event"] == "delta")
    assert meta["data"]["action"] == non_stream.json()["action"]
    assert deltas == non_stream.json()["reply_text"]


def test_delete_other_user_memory_403(e2e):
    client, factory = e2e
    with factory() as db:
        m = Memory(user_id="other_user", layer="event", content="别人的记忆", importance=3)
        db.add(m)
        db.commit()
        mid = m.id
    token = create_token("demo_user_1", "elder", SECRET)
    resp = client.delete(f"/api/memories/{mid}", headers=_auth(token))
    assert resp.status_code == 403


def test_category_sort_questions_no_answer_leak(e2e):
    client, _ = e2e
    token = create_token("demo_user_1", "elder", SECRET)
    resp = client.post("/api/game/start", json={"game_type": "category_sort"}, headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert 1 <= data["difficulty"] <= 3
    questions = data["items"]["questions"]
    assert questions
    for q in questions:
        assert "answer" not in q
