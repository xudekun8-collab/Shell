"""三层记忆测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.db.models import Conversation, InteractionEvent, Memory, Profile
from app.llm.client import FakeClient
from app.llm.prompts import build_system_prompt
from app.memory.compress import maybe_compress
from app.memory.store import recall, write_event_memory, write_profile


@pytest.fixture()
def factory():
    engine = create_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_event_memory_recall_in_same_thread(factory):
    write_event_memory({"user_id": "demo_user_1", "raw_input": "我孙女上周末来看我了，带了点心"}, factory)
    got = recall("demo_user_1", "我孙女啥时候来过", session_factory=factory)
    assert got and "孙女" in got[0]["content"]


def test_soft_delete_hides_from_recall(factory):
    write_event_memory({"user_id": "demo_user_1", "raw_input": "我孙女上周末来看我了"}, factory)
    got = recall("demo_user_1", "孙女", session_factory=factory)
    assert got
    with factory() as session:
        memory = session.get(Memory, got[0]["memory_id"])
        memory.is_deleted = 1
        session.commit()
    assert recall("demo_user_1", "孙女", session_factory=factory) == []


def test_compress_when_msg_count_exceeds(factory):
    with factory() as session:
        session.add(Conversation(id="t1", user_id="demo_user_1", msg_count=21))
        for i in range(21):
            session.add(
                InteractionEvent(
                    user_id="demo_user_1",
                    thread_id="t1",
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
    assert maybe_compress("t1", FakeClient(), session_factory=factory)
    with factory() as session:
        conv = session.get(Conversation, "t1")
        assert conv.msg_count == 0
        assert len(conv.summary) <= 100


def test_write_taboo_appears_in_prompt(factory):
    write_profile({"user_id": "demo_user_1", "raw_input": "别提我老伴"}, factory)
    with factory() as session:
        profile = session.get(Profile, "demo_user_1")
        prompt = build_system_prompt(
            {"profile": {"nickname": profile.nickname, "interests": profile.interests, "taboos": profile.taboos}}
        )
    assert "我老伴" in prompt
