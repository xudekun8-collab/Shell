"""游戏引擎与难度自适应测试。"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db.models import TrainingRecord
from app.services import game_engine
from app.services.difficulty import next_difficulty

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "game_items"


def _add_record(factory, user_id, game_type, difficulty, correct, total, duration, abandoned=0, minutes_ago=0):
    with factory() as db:
        db.add(
            TrainingRecord(
                user_id=user_id,
                game_type=game_type,
                difficulty=difficulty,
                correct_count=correct,
                total_count=total,
                duration_sec=duration,
                abandoned=abandoned,
                created_at=datetime.now() - timedelta(minutes=minutes_ago),
            )
        )
        db.commit()


def test_question_bank_self_check():
    for game_type, filename in [("memory_box", "memory_box.json"), ("category_sort", "category_sort.json")]:
        data = json.loads((_DATA_DIR / filename).read_text(encoding="utf-8"))
        for level, groups in data.items():
            for group in groups:
                if game_type == "memory_box":
                    show = set(group["show_items"])
                    for q in group["quizzes"]:
                        if q["appeared"]:
                            assert q["target"] in show
                        else:
                            assert q["target"] not in show
                else:
                    assert group["answer"] in group["options"]


def _start(factory, user_id, game_type):
    with factory() as db:
        return game_engine.start(user_id, game_type, db)


def _submit(factory, session_id, answers, duration=10, abandoned=False):
    with factory() as db:
        return game_engine.submit(session_id, answers, duration, abandoned, db)


def test_judging_all_wrong_partial(factory):
    start = _start(factory, "u1", "memory_box")
    quizzes = start["items"]["quizzes"]
    all_correct = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes)]
    r = _submit(factory, start["session_id"], all_correct)
    assert r["correct"] == r["total"] == len(quizzes)

    start2 = _start(factory, "u1", "memory_box")
    quizzes2 = start2["items"]["quizzes"]
    all_wrong = [{"index": i, "value": not q["appeared"]} for i, q in enumerate(quizzes2)]
    r2 = _submit(factory, start2["session_id"], all_wrong)
    assert r2["correct"] == 0
    assert r2["total"] == len(quizzes2)

    start3 = _start(factory, "u1", "memory_box")
    quizzes3 = start3["items"]["quizzes"]
    partial = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes3) if i % 2 == 0]
    r3 = _submit(factory, start3["session_id"], partial)
    expect_correct = sum(1 for i, q in enumerate(quizzes3) if i % 2 == 0)
    assert r3["correct"] == expect_correct
    assert r3["total"] == len(quizzes3)


def test_unanswered_counts_as_wrong(factory):
    start = _start(factory, "u1", "memory_box")
    total = len(start["items"]["quizzes"])
    r = _submit(factory, start["session_id"], [])
    assert r["correct"] == 0
    assert r["total"] == total


def test_low_accuracy_drops(factory):
    for i in range(3):
        _add_record(factory, "u2", "memory_box", 2, 0, 4, 10, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("u2", "memory_box", db) == 1


def test_abandoned_signal_2_to_1(factory):
    # 对应「太难了」按钮回归：2 档最近 1 条放弃（该局 5/8），先降一档不看 acc
    _add_record(factory, "a1", "memory_box", 2, 5, 8, 10, abandoned=1, minutes_ago=0)
    for i in range(1, 5):
        _add_record(factory, "a1", "memory_box", 2, 4, 4, 10, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("a1", "memory_box", db) == 1


def test_abandoned_signal_3_to_2(factory):
    _add_record(factory, "a2", "memory_box", 3, 5, 8, 10, abandoned=1, minutes_ago=0)
    for i in range(1, 5):
        _add_record(factory, "a2", "memory_box", 3, 4, 4, 10, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("a2", "memory_box", db) == 2


def test_abandoned_signal_1_stay(factory):
    _add_record(factory, "a3", "memory_box", 1, 0, 4, 10, abandoned=1, minutes_ago=0)
    for i in range(1, 5):
        _add_record(factory, "a3", "memory_box", 1, 0, 4, 10, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("a3", "memory_box", db) == 1


def test_all_abandoned_fallback(factory):
    for i in range(5):
        _add_record(factory, "a4", "memory_box", 2, 5, 8, 10, abandoned=1, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("a4", "memory_box", db) == 1


def test_abandoned_excluded_from_acc(factory):
    # 4 条正常 0.90 + 1 条放弃（最老，不在最近 3 条里），放弃不参与 acc → 应升档
    for i in range(4):
        _add_record(factory, "a5", "memory_box", 2, 9, 10, 10, minutes_ago=i)
    _add_record(factory, "a5", "memory_box", 2, 0, 10, 10, abandoned=1, minutes_ago=4)
    with factory() as db:
        assert next_difficulty("a5", "memory_box", db) == 3


def test_high_accuracy_fast_raises(factory):
    for i in range(3):
        _add_record(factory, "u4", "memory_box", 1, 4, 4, 1, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("u4", "memory_box", db) == 2


def test_clamp_bounds(factory):
    for i in range(3):
        _add_record(factory, "u5", "memory_box", 1, 0, 4, 10, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("u5", "memory_box", db) == 1
    for i in range(3):
        _add_record(factory, "u6", "memory_box", 3, 4, 4, 1, minutes_ago=i)
    with factory() as db:
        assert next_difficulty("u6", "memory_box", db) == 3


def _add_window(factory, user_id, difficulty, correct, total, n=5):
    for i in range(n):
        _add_record(factory, user_id, "memory_box", difficulty, correct, total, 10, minutes_ago=i)


def test_entry_2_stay_at_070(factory):
    _add_window(factory, "d1", 2, 7, 10)
    with factory() as db:
        assert next_difficulty("d1", "memory_box", db) == 2


def test_entry_1_climb_to_2_at_070(factory):
    # 死区回归：1 档下 0.70 能达到 2 档门槛，必须能爬回 2 档
    _add_window(factory, "d2", 1, 7, 10)
    with factory() as db:
        assert next_difficulty("d2", "memory_box", db) == 2


def test_entry_2_climb_to_3_at_090(factory):
    _add_window(factory, "d3", 2, 9, 10)
    with factory() as db:
        assert next_difficulty("d3", "memory_box", db) == 3


def test_entry_3_drop_to_2_at_080(factory):
    _add_window(factory, "d4", 3, 8, 10)
    with factory() as db:
        assert next_difficulty("d4", "memory_box", db) == 2


def test_entry_2_drop_to_1_at_050(factory):
    _add_window(factory, "d5", 2, 5, 10)
    with factory() as db:
        assert next_difficulty("d5", "memory_box", db) == 1


def test_entry_1_stay_at_030(factory):
    _add_window(factory, "d6", 1, 3, 10)
    with factory() as db:
        assert next_difficulty("d6", "memory_box", db) == 1


def test_only_recent_five_used(factory):
    # 最老 1 条是 0 分，但窗口只取最近 5 条（0.70），不影响结果
    _add_window(factory, "d7", 2, 7, 10, n=5)
    _add_record(factory, "d7", "memory_box", 2, 0, 10, 10, minutes_ago=5)
    with factory() as db:
        assert next_difficulty("d7", "memory_box", db) == 2


def test_less_than_three_returns_two(factory):
    with factory() as db:
        assert next_difficulty("d8", "memory_box", db) == 2
    _add_record(factory, "d8", "memory_box", 2, 0, 10, 10, minutes_ago=0)
    with factory() as db:
        assert next_difficulty("d8", "memory_box", db) == 2
    _add_record(factory, "d8", "memory_box", 2, 0, 10, 10, minutes_ago=0)
    with factory() as db:
        assert next_difficulty("d8", "memory_box", db) == 2


def test_record_written(factory):
    with factory() as db:
        before = db.execute(select(func.count()).select_from(TrainingRecord)).scalar()
    start = _start(factory, "u7", "memory_box")
    quizzes = start["items"]["quizzes"]
    answers = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes)]
    _submit(factory, start["session_id"], answers)
    with factory() as db:
        after = db.execute(select(func.count()).select_from(TrainingRecord)).scalar()
    assert after == before + 1


def test_submit_missing_session_404(factory, monkeypatch):
    import app.api.games as games_mod
    from fastapi.testclient import TestClient

    monkeypatch.setattr(games_mod, "SessionLocal", factory)
    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/game/submit",
        json={"session_id": "nope", "answers": [], "duration_sec": 0, "abandoned": False},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "会话已失效，请重新开始"


def _cat_answer_map():
    bank = json.loads((_DATA_DIR / "category_sort.json").read_text(encoding="utf-8"))
    m = {}
    for groups in bank.values():
        for g in groups:
            m[g["id"]] = g["answer"]
    return m


def test_category_sort_question_counts(factory):
    with factory() as db:
        start = game_engine.start("cs_mid_u", "category_sort", db)
    assert len(start["items"]["questions"]) == 8

    for i in range(3):
        _add_record(factory, "cs_low_u", "category_sort", 1, 0, 3, 10, minutes_ago=i)
    with factory() as db:
        start = game_engine.start("cs_low_u", "category_sort", db)
    assert len(start["items"]["questions"]) == 6

    for i in range(3):
        _add_record(factory, "cs_high_u", "category_sort", 3, 3, 3, 1, minutes_ago=i)
    with factory() as db:
        start = game_engine.start("cs_high_u", "category_sort", db)
    assert len(start["items"]["questions"]) == 10


def test_category_sort_ids_unique(factory):
    with factory() as db:
        start = game_engine.start("cs_uniq_u", "category_sort", db)
    ids = [q["id"] for q in start["items"]["questions"]]
    assert len(ids) == len(set(ids))


def test_category_sort_judging(factory):
    id_answer = _cat_answer_map()
    with factory() as db:
        start = game_engine.start("cs_j1", "category_sort", db)
    qs = start["items"]["questions"]
    all_correct = [{"index": i, "value": id_answer[q["id"]]} for i, q in enumerate(qs)]
    with factory() as db:
        r = game_engine.submit(start["session_id"], all_correct, 5, False, db)
    assert r["correct"] == r["total"] == len(qs)

    with factory() as db:
        start2 = game_engine.start("cs_j2", "category_sort", db)
    qs2 = start2["items"]["questions"]
    all_wrong = [
        {"index": i, "value": next(o for o in q["options"] if o != id_answer[q["id"]])}
        for i, q in enumerate(qs2)
    ]
    with factory() as db:
        r2 = game_engine.submit(start2["session_id"], all_wrong, 5, False, db)
    assert r2["correct"] == 0
    assert r2["total"] == len(qs2)

    with factory() as db:
        start3 = game_engine.start("cs_j3", "category_sort", db)
    qs3 = start3["items"]["questions"]
    partial = [
        {"index": i, "value": id_answer[q["id"]] if i % 2 == 0 else next(o for o in q["options"] if o != id_answer[q["id"]])}
        for i, q in enumerate(qs3)
    ]
    with factory() as db:
        r3 = game_engine.submit(start3["session_id"], partial, 5, False, db)
    assert r3["correct"] == sum(1 for i in range(len(qs3)) if i % 2 == 0)
    assert r3["total"] == len(qs3)


def test_category_sort_missing_answers(factory):
    id_answer = _cat_answer_map()
    with factory() as db:
        start = game_engine.start("cs_j4", "category_sort", db)
    qs = start["items"]["questions"]
    submit_count = len(qs) - 3
    answers = [{"index": i, "value": id_answer[q["id"]]} for i, q in enumerate(qs[:submit_count])]
    with factory() as db:
        r = game_engine.submit(start["session_id"], answers, 5, False, db)
    assert r["total"] == len(qs)
    assert r["correct"] == submit_count


def test_category_sort_no_answer_leak(factory):
    with factory() as db:
        start = game_engine.start("cs_j5", "category_sort", db)
    for q in start["items"]["questions"]:
        assert "answer" not in q


def test_category_sort_bank_counts():
    bank = json.loads((_DATA_DIR / "category_sort.json").read_text(encoding="utf-8"))
    assert len(bank["low"]) == 10
    assert len(bank["mid"]) == 12
    assert len(bank["high"]) == 12
    for groups in bank.values():
        for g in groups:
            assert g["answer"] in g["options"]
