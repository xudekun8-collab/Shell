"""接口级端到端测试：一条主链 + 若干反向用例，全部走内存 SQLite + FakeClient。"""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.agent.rules import SAFETY_TEMPLATES
from app.db.init_db import init_db
from app.db.models import Conversation, FamilyBind, InteractionEvent, Memory, TrainingRecord
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
    import app.api.family as family_mod
    import app.api.games as games_mod
    import app.api.greeting as greeting_mod
    import app.api.memory as memory_mod
    import app.api.records as records_mod
    from app.agent.graph import build_graph
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

    for mod in (
        chat_mod,
        records_mod,
        memory_mod,
        games_mod,
        greeting_mod,
        auth_mod,
        context_mod,
        family_mod,
    ):
        monkeypatch.setattr(mod, "SessionLocal", factory)

    fake = FakeClient()
    monkeypatch.setattr(chat_mod, "_llm_client", fake)
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
    with factory() as db:
        db.add(
            TrainingRecord(
                user_id="demo_user_1",
                game_type="memory_box",
                difficulty=1,
                correct_count=0,
                total_count=2,
                duration_sec=999,
                abandoned=1,
            )
        )
        db.commit()
    rec2 = client.get("/api/records", headers=headers)
    assert rec2.status_code == 200
    rj2 = rec2.json()
    assert any(record["abandoned"] == 1 for record in rj2["records"])
    assert rj2["summary"]["total"] == 1
    assert rj2["summary"]["total_duration"] == 20
    assert rj2["summary"]["by_type"] == [
        {"game_type": "memory_box", "total": 1, "avg_accuracy": 100}
    ]
    legacy = client.get("/api/records/demo_user_1")
    assert legacy.status_code == 200
    assert legacy.json()["summary"] == rj2["summary"]
    with factory() as db:
        db.add(
            FamilyBind(
                elder_id="demo_user_1",
                family_user_id="family_e2e",
                invite_code="80000001",
                expires_at=datetime.now() + timedelta(days=1),
                bound_at=datetime.now(),
            )
        )
        db.commit()
    family_headers = _auth(create_token("family_e2e", "family", SECRET))
    family_records = client.get("/api/family/records", headers=family_headers)
    assert family_records.status_code == 200
    fr = family_records.json()
    assert fr["total"] == rj2["summary"]["total"]
    assert fr["avg_accuracy"] == rj2["summary"]["avg_accuracy"]
    assert any(record["abandoned"] == 1 for record in fr["records"])
    other_headers = _auth(create_token("other_demo", "elder", SECRET))
    with factory() as db:
        before_count = db.execute(
            select(func.count())
            .select_from(InteractionEvent)
            .where(InteractionEvent.thread_id == "e2e")
        ).scalar()
        before_msg_count = db.get(Conversation, "e2e").msg_count
    other_chat = client.post(
        "/api/chat",
        json={"thread_id": "e2e", "text": "另一个账号也不能接管这个会话"},
        headers=other_headers,
    )
    assert other_chat.status_code == 403
    with factory() as db:
        conversation = db.get(Conversation, "e2e")
        assert conversation.user_id == "demo_user_1"
        assert conversation.msg_count == before_msg_count
        after_count = db.execute(
            select(func.count())
            .select_from(InteractionEvent)
            .where(InteractionEvent.thread_id == "e2e")
        ).scalar()
        assert after_count == before_count

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


def test_chat_rejects_oversized_input(e2e):
    client, _ = e2e
    headers = _auth(create_token("demo_user_1", "elder", SECRET))
    too_long_text = client.post(
        "/api/chat",
        json={"thread_id": "limit", "text": "话" * 1001},
        headers=headers,
    )
    too_long_thread = client.post(
        "/api/chat",
        json={"thread_id": "t" * 65, "text": "你好"},
        headers=headers,
    )
    assert too_long_text.status_code == 422
    assert too_long_thread.status_code == 422


def test_chat_stream_rejects_other_users_thread(e2e):
    client, factory = e2e
    with factory() as db:
        db.add(Conversation(id="owned", user_id="owner", msg_count=0))
        db.commit()
    response = client.post(
        "/api/chat/stream",
        json={"thread_id": "owned", "text": "你好"},
        headers=_auth(create_token("other", "elder", SECRET)),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "会话不属于当前用户"


def test_public_family_bind_returns_working_token(e2e):
    client, _ = e2e
    elder_headers = _auth(create_token("demo_user_1", "elder", SECRET))
    invite = client.post("/api/family/invite", headers=elder_headers)
    assert invite.status_code == 200
    bound = client.post("/api/family/bind", json={"invite_code": invite.json()["invite_code"]})
    assert bound.status_code == 200
    assert bound.json()["elder_id"] == "demo_user_1"
    overview = client.get(
        "/api/family/overview",
        headers=_auth(bound.json()["token"]),
    )
    assert overview.status_code == 200


def test_family_invite_can_only_be_bound_once(e2e):
    client, _ = e2e
    elder_headers = _auth(create_token("demo_user_1", "elder", SECRET))
    invite = client.post("/api/family/invite", headers=elder_headers)
    code = invite.json()["invite_code"]
    assert client.post("/api/family/bind", json={"invite_code": code}).status_code == 200
    second = client.post("/api/family/bind", json={"invite_code": code})
    assert second.status_code == 400
    assert second.json()["detail"] == "邀请码无效或已用过"


def test_family_bind_sixth_failure_from_same_ip_429(e2e):
    client, _ = e2e
    for attempt in range(5):
        response = client.post(
            "/api/family/bind",
            json={"invite_code": f"bad-{attempt}"},
        )
        assert response.status_code == 400
    sixth = client.post("/api/family/bind", json={"invite_code": "bad-5"})
    assert sixth.status_code == 429
    assert sixth.json()["detail"] == "试的次数太多了，过一会再试"


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
