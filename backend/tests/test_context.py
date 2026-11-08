"""多轮上下文、累积压缩与召回门槛测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.context import recent_turns
from app.agent.graph import build_graph
from app.db.init_db import init_db
from app.db.models import Conversation, InteractionEvent
from app.llm.client import FakeClient
from app.memory.compress import maybe_compress
from app.memory.store import recall, write_event_memory


@pytest.fixture()
def factory():
    engine = create_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _add_event(factory, thread_id, raw, reply):
    with factory() as session:
        session.add(
            InteractionEvent(
                user_id="demo_user_1",
                thread_id=thread_id,
                input_type="text",
                raw_input=raw,
                perceived={},
                action="reply",
                reason="",
                reply_text=reply,
                latency_ms=1,
            )
        )
        session.commit()


def test_recent_dialogue_contains_previous_turns(factory):
    _add_event(factory, "t1", "今天天气不错", "我听着呢")
    _add_event(factory, "t1", "我今天心里有点闷", "您说")
    recent = recent_turns("demo_user_1", "t1", session_factory=factory)
    assert any("今天天气不错" in t for t in recent)
    assert any("我今天心里有点闷" in t for t in recent)
    graph = build_graph(FakeClient(), factory)
    result = graph.invoke(
        {
            "user_id": "demo_user_1",
            "thread_id": "t1",
            "raw_input": "我刚才说啥了",
            "input_type": "text",
            "recent_dialogue": recent,
        }
    )
    assert "我今天心里有点闷" in " ".join(result.get("recent_dialogue", []))


def test_compress_at_ninth_turn(factory):
    with factory() as session:
        session.add(Conversation(id="t2", user_id="demo_user_1", msg_count=9))
        for i in range(9):
            session.add(
                InteractionEvent(
                    user_id="demo_user_1",
                    thread_id="t2",
                    input_type="text",
                    raw_input=f"第{i}句",
                    perceived={},
                    action="reply",
                    reason="",
                    reply_text=f"回{i}",
                    latency_ms=1,
                )
            )
        session.commit()
    assert maybe_compress("t2", FakeClient(), session_factory=factory)
    with factory() as session:
        conv = session.get(Conversation, "t2")
        assert conv.summary and len(conv.summary) <= 100
        assert conv.msg_count == 0


def test_compress_cumulative_keeps_first_round(factory):
    with factory() as session:
        session.add(Conversation(id="t3", user_id="demo_user_1", msg_count=8))
        session.add(
            InteractionEvent(
                user_id="demo_user_1",
                thread_id="t3",
                input_type="text",
                raw_input="我孙女上周末来看我",
                perceived={},
                action="reply",
                reason="",
                reply_text="真好啊",
                latency_ms=1,
            )
        )
        for i in range(1, 8):
            session.add(
                InteractionEvent(
                    user_id="demo_user_1",
                    thread_id="t3",
                    input_type="text",
                    raw_input=f"第{i}句",
                    perceived={},
                    action="reply",
                    reason="",
                    reply_text=f"回{i}",
                    latency_ms=1,
                )
            )
        session.commit()
    assert maybe_compress("t3", FakeClient(), session_factory=factory)
    with factory() as session:
        first_summary = session.get(Conversation, "t3").summary
    assert "孙女" in first_summary
    with factory() as session:
        conv = session.get(Conversation, "t3")
        conv.msg_count = 8
        for i in range(8):
            session.add(
                InteractionEvent(
                    user_id="demo_user_1",
                    thread_id="t3",
                    input_type="text",
                    raw_input=f"新第{i}句",
                    perceived={},
                    action="reply",
                    reason="",
                    reply_text=f"新回{i}",
                    latency_ms=1,
                )
            )
        session.commit()
    assert maybe_compress("t3", FakeClient(), session_factory=factory)
    with factory() as session:
        final_summary = session.get(Conversation, "t3").summary
    assert "孙女" in final_summary


def test_unrelated_query_does_not_recall(factory):
    write_event_memory({"user_id": "demo_user_1", "raw_input": "我孙女上周末来看我了，带了点心"}, factory)
    assert recall("demo_user_1", "今天吃什么", session_factory=factory) == []
