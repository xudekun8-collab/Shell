"""规则闸门测试：夜间免打扰 R2。"""
from datetime import time

from app.agent.actions import ACTION_REMIND
from app.agent.rules import filter_actions


def _state() -> dict:
    return {
        "raw_input": "今天天气怎么样",
        "profile": {"sleep_time": "22:00:00", "wake_time": "07:00:00"},
    }


def test_r2_night_removes_remind():
    allowed, forced, _ = filter_actions(_state(), now=time(23, 30))
    assert ACTION_REMIND not in allowed
    assert forced is None


def test_r2_day_keeps_remind():
    allowed, forced, _ = filter_actions(_state(), now=time(14, 0))
    assert ACTION_REMIND in allowed
    assert forced is None


def test_r2_boundaries_remove_remind():
    for t in (time(22, 0), time(7, 0)):
        allowed, _, _ = filter_actions(_state(), now=t)
        assert ACTION_REMIND not in allowed
