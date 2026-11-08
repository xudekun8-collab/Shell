"""五类安全规则测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.rules import SAFETY_TEMPLATES, match_safety
from app.db.init_db import init_db
from app.llm.client import FakeClient


@pytest.mark.parametrize("text,category", [
    ("这药能不能少吃点", "medical"),
    ("我上周的检查结果出来了", "medical"),
    ("有人让我转账到一个安全账户", "finance"),
    ("我中奖了，要先交手续费", "finance"),
    ("我想立一份遗嘱", "legal"),
    ("房子要办房产过户", "legal"),
    ("我老伴去世三年了", "bereavement"),
    ("我想他了，心里难受", "bereavement"),
    ("我不想活了", "crisis"),
    ("我整宿睡不着，一个人难受", "crisis"),
])
def test_safety_hit(text, category):
    matched = match_safety(text)
    assert matched is not None
    assert matched["category"] == category
    assert 30 <= len(matched["template"]) <= 80


@pytest.mark.parametrize("text", [
    "我今天胃口不错",
    "我今天买了点水果",
    "我明天去社区开会",
    "我今天心情不错",
    "我今天有点困",
])
def test_safety_no_hit(text):
    assert match_safety(text) is None


def test_hospital_friend_not_medical():
    assert match_safety("我昨天去医院看了个朋友") is None


def test_severity_priority():
    matched = match_safety("我不想活了，这药也没用")
    assert matched["category"] == "crisis"
    assert matched["severity"] == 3


def test_crisis_writes_effect():
    engine = create_engine("sqlite://")
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    graph = build_graph(FakeClient(), factory)
    result = graph.invoke(
        {"user_id": "demo_user_1", "thread_id": "t1", "raw_input": "我不想活了", "input_type": "text"}
    )
    assert result["plan"]["action"] == "reply"
    assert result["reply_text"] == SAFETY_TEMPLATES["crisis"]
    assert "safety_crisis_3" in result.get("effects", [])


@pytest.mark.parametrize("text", [
    "我出去走了走，天气挺好",
    "我先走了啊，回头再聊",
    "我去药店买了点感冒药",
    "这药一个月要好几百块钱",
    "这药医保能报销吗",
    "这电视剧没意思",
    "下棋没意思，换个别的",
    "我儿子在银行做投资",
    "中午吃了点剩饭，胃有点不舒服",
    "我昨天去医院看了个朋友",
    "我在小区里走了几圈",
    "电视里说有个老人吃错药了",
])
def test_safety_false_positive(text):
    assert match_safety(text) is None


@pytest.mark.parametrize("text,category", [
    ("这药能不能少吃点", "medical"),
    ("我老伴走了半年了，晚上总睡不着", "bereavement"),
    ("活着真没意思，不如算了", "crisis"),
])
def test_safety_regression_hit(text, category):
    matched = match_safety(text)
    assert matched is not None
    assert matched["category"] == category


def test_crisis_regression_effect():
    engine = create_engine("sqlite://")
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    graph = build_graph(FakeClient(), factory)
    result = graph.invoke(
        {"user_id": "demo_user_1", "thread_id": "t2", "raw_input": "活着真没意思，不如算了", "input_type": "text"}
    )
    assert result["plan"]["action"] == "reply"
    assert result["reply_text"] == SAFETY_TEMPLATES["crisis"]
    assert "safety_crisis_3" in result.get("effects", [])
