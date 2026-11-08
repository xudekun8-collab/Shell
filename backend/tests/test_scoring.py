"""打分函数单测。"""
from datetime import date, timedelta

from app.memory.scoring import score_memory, time_prefilter


def test_overlap_ordering():
    query = "我孙女来看我"
    full = score_memory(query, "我孙女上周来看我", 3, date.today(), "event")
    partial = score_memory(query, "我孙女昨天吃了点心", 3, date.today(), "event")
    irrelevant = score_memory(query, "昨天去买了菜", 3, date.today(), "event")
    assert full > partial > irrelevant


def test_time_prefilter():
    query = "我上周去医院复查眼睛"
    assert time_prefilter(query, date.today() - timedelta(days=7)) is True
    assert time_prefilter(query, date.today()) is False


def test_importance_ordering():
    query = "我孙女来看我"
    high = score_memory(query, "我孙女来看我", 5, date.today(), "event")
    low = score_memory(query, "我孙女来看我", 1, date.today(), "event")
    assert high > low
