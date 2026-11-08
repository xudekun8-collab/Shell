"""按时间主动问候的规则测试（内存 SQLite，不连 MySQL）。"""
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import Conversation, InteractionEvent, Profile
from app.services.greeting import build_greeting, period_of


def _now(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 8, hour, minute, 0)


def test_five_periods_return_expected_sentences(factory):
    """五个时段各返回对应句子；用无兴趣画像避免 evening 追加。"""
    session = factory()
    with session as db:
        profile = Profile(user_id="u1", nickname="王大爷", interests=[], taboos=[])
        db.add(profile)
        db.commit()
        cases = [
            (_now(7), "morning", "王大爷，早上好。昨晚睡得踏实不踏实？"),
            (_now(12), "noon", "王大爷，该吃饭了，今天想吃点啥？"),
            (_now(15), "afternoon", "王大爷，下午这会儿闲着没？陪我说说话吧。"),
            (_now(19), "evening", "王大爷，今天有啥高兴的事儿？"),
            (_now(23), "night", "王大爷，夜深了，早点歇着，明天我再来陪您。"),
        ]
        for now, period, text in cases:
            result = build_greeting(profile, now)
            assert result["period"] == period
            assert result["greeting"] == text


def test_night_window_covers_22_and_03(factory):
    session = factory()
    with session as db:
        profile = Profile(user_id="u2", nickname="李奶奶", interests=[], taboos=[])
        db.add(profile)
        db.commit()
        assert build_greeting(profile, _now(22))["period"] == "night"
        assert build_greeting(profile, _now(3))["period"] == "night"


def test_boundary_1059_morning_1100_noon():
    assert period_of(_now(10, 59)) == "morning"
    assert period_of(_now(11, 0)) == "noon"


def test_nickname_used_or_fallback(factory):
    session = factory()
    with session as db:
        named = Profile(user_id="u3", nickname="赵叔", interests=[], taboos=[])
        unnamed = Profile(user_id="u4", nickname="", interests=[], taboos=[])
        db.add_all([named, unnamed])
        db.commit()
        named_result = build_greeting(named, _now(7))
        unnamed_result = build_greeting(unnamed, _now(7))
        none_result = build_greeting(None, _now(7))
    assert "赵叔" in named_result["greeting"]
    assert "赵叔" not in unnamed_result["greeting"]
    assert unnamed_result["greeting"].startswith("您")
    assert none_result["greeting"].startswith("您")


def test_evening_appends_interest_only_when_present(factory):
    session = factory()
    with session as db:
        with_interest = Profile(user_id="u5", nickname="孙姨", interests=["京剧"], taboos=[])
        without_interest = Profile(user_id="u6", nickname="孙姨", interests=[], taboos=[])
        db.add_all([with_interest, without_interest])
        db.commit()
        r1 = build_greeting(with_interest, _now(19))
        r2 = build_greeting(without_interest, _now(19))
    assert r1["greeting"] == "孙姨，今天有啥高兴的事儿？您上次说喜欢京剧，还惦记着吗？"
    assert r2["greeting"] == "孙姨，今天有啥高兴的事儿？"


def _call_greeting(factory, thread_id=None):
    """直接调用路由处理函数，用内存 SQLite 会话工厂替换 SessionLocal。"""
    import app.api.greeting as greeting_api

    original = greeting_api.SessionLocal
    greeting_api.SessionLocal = factory
    try:
        return greeting_api.get_greeting({"user_id": "demo_user_1"}, thread_id=thread_id)
    finally:
        greeting_api.SessionLocal = original


def test_greeting_with_thread_id_records_one_turn(factory):
    resp = _call_greeting(factory, thread_id="t1")
    assert resp.greeting
    with factory() as db:
        events = db.execute(
            select(InteractionEvent).where(InteractionEvent.thread_id == "t1")
        ).scalars().all()
        assert len(events) == 1
        assert events[0].input_type == "greeting"
        assert events[0].reply_text == resp.greeting
        conv = db.get(Conversation, "t1")
        assert conv is not None
        assert conv.msg_count == 0


def test_greeting_without_thread_id_writes_nothing(factory):
    resp = _call_greeting(factory)
    assert resp.greeting
    with factory() as db:
        conv_count = db.execute(select(func.count()).select_from(Conversation)).scalar()
        ev_count = db.execute(select(func.count()).select_from(InteractionEvent)).scalar()
        assert conv_count == 0
        assert ev_count == 0


def test_greeting_twice_records_exactly_two_turns(factory):
    _call_greeting(factory, thread_id="t1")
    _call_greeting(factory, thread_id="t1")
    with factory() as db:
        events = db.execute(
            select(InteractionEvent).where(InteractionEvent.thread_id == "t1")
        ).scalars().all()
        assert len(events) == 2
        conv = db.get(Conversation, "t1")
        assert conv.msg_count == 0
