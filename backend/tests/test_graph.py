"""状态图测试：假模型下验证三条关键路径。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.actions import ACTION_END, ACTION_REPLY
from app.agent.graph import build_graph
from app.agent.rules import SAFETY_TEMPLATES
from app.db.init_db import init_db
from app.llm.client import FakeClient


class CountingFakeClient(FakeClient):
    def __init__(self):
        self.calls = 0

    def plan(self, state):
        self.calls += 1
        return super().plan(state)


@pytest.fixture()
def graph():
    engine = create_engine("sqlite://")
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = CountingFakeClient()
    return build_graph(client, factory), client


def _run(graph, text: str) -> dict:
    return graph.invoke(
        {
            "user_id": "demo_user_1",
            "thread_id": "t1",
            "raw_input": text,
            "input_type": "text",
        }
    )


def test_chitchat_replies(graph):
    g, _ = graph
    result = _run(g, "今天天气不错")
    assert result["plan"]["action"] == ACTION_REPLY


def test_end_skips_llm(graph):
    g, client = graph
    result = _run(g, "不聊了")
    assert result["plan"]["action"] == ACTION_END
    assert client.calls == 0


def test_medical_forces_referral(graph):
    g, _ = graph
    result = _run(g, "这药能不能少吃点")
    assert result["plan"]["action"] == ACTION_REPLY
    assert result["reply_text"] == SAFETY_TEMPLATES["medical"]
