"""训练记录连续天数测试。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api.records import streak_days
from app.db.models import TrainingRecord


def _row(days_ago: int, *, abandoned: int = 0, total: int = 4):
    return SimpleNamespace(
        created_at=datetime.now() - timedelta(days=days_ago),
        abandoned=abandoned,
        total_count=total,
        correct_count=3,
    )


def test_streak_counts_consecutive_days_ending_today():
    rows = [_row(0), _row(1), _row(2), _row(2)]
    assert streak_days(rows) == 3


def test_streak_starts_from_yesterday_when_today_has_no_practice():
    rows = [_row(1), _row(2), _row(4)]
    assert streak_days(rows) == 2


def test_streak_counts_answered_incomplete_sessions_but_not_empty_ones():
    rows = [
        _row(0),
        _row(1, abandoned=1),
        _row(2, total=0),
        _row(3),
    ]
    assert streak_days(rows) == 2


def test_streak_stops_at_first_missing_day():
    rows = [_row(0), _row(2), _row(3)]
    assert streak_days(rows) == 1


def test_records_summary_exposes_streak_days(factory, monkeypatch):
    import app.api.records as records_api

    monkeypatch.setattr(records_api, "SessionLocal", factory)
    with factory() as db:
        for days_ago, abandoned in ((0, 0), (1, 0), (2, 1)):
            db.add(
                TrainingRecord(
                    user_id="streak_user",
                    game_type="memory_box",
                    difficulty=1,
                    correct_count=3,
                    total_count=4,
                    duration_sec=20,
                    abandoned=abandoned,
                    created_at=datetime.now() - timedelta(days=days_ago),
                )
            )
        db.commit()
    response = records_api.get_records({"user_id": "streak_user"})
    assert response.summary.streak_days == 3
    assert response.summary.total == 2
