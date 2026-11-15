"""游戏注册表、新题型和提交明细测试。"""
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db.models import TrainingRecord
from app.services import game_engine, game_session
from app.services.difficulty import time_limit
from app.services.games import GAME_REGISTRY, UnknownGameError
from app.services.token import create_token

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "game_items"
SEED = 20261108
FORBIDDEN_EXPLANATION_WORDS = ("记忆力下降", "认知障碍", "您这个年纪", "记性不好")


def _digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _start(factory, user_id, game_type):
    with factory() as db:
        return game_engine.start(user_id, game_type, db)


def _submit(factory, session_id, answers):
    with factory() as db:
        return game_engine.submit(session_id, answers, 10, False, db)


def _add_records(factory, user_id, game_type, difficulty, total, correct, count=3):
    with factory() as db:
        for index in range(count):
            db.add(
                TrainingRecord(
                    user_id=user_id,
                    game_type=game_type,
                    difficulty=difficulty,
                    correct_count=correct,
                    total_count=total,
                    duration_sec=10,
                    abandoned=0,
                    created_at=datetime.now() - timedelta(minutes=index),
                )
            )
        db.commit()


def test_registry_contains_four_games():
    assert set(GAME_REGISTRY) == {"memory_box", "category_sort", "number_seq", "common_sense"}
    for module in GAME_REGISTRY.values():
        assert callable(module.generate)
        assert callable(module.judge)
        assert set(module.TIME_LIMIT) == {1, 2, 3}


def test_unknown_game_does_not_use_default_time_limit():
    with pytest.raises(UnknownGameError):
        time_limit("unknown_game", 2)


def test_expired_game_session_is_removed_on_get(monkeypatch):
    session_id = game_session.create("expiry_user", "memory_box", 2, {"questions": []})
    monkeypatch.setattr(game_session, "_TTL_SECONDS", 0)
    game_session._SESSIONS[session_id]["started_at"] -= 1
    assert game_session.get(session_id) is None


def test_unknown_game_start_400(factory, monkeypatch):
    import app.api.games as games_api

    monkeypatch.setattr(games_api, "SessionLocal", factory)
    monkeypatch.setattr(config, "AUTH_SECRET", "registry-test-secret")
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    token = create_token("unknown_user", "elder", "registry-test-secret")
    response = client.post(
        "/api/game/start",
        json={"game_type": "unknown_game"},
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "未知题型"


def test_unknown_session_game_submit_400(factory, monkeypatch):
    import app.api.games as games_api

    monkeypatch.setattr(games_api, "SessionLocal", factory)
    monkeypatch.setattr(config, "AUTH_SECRET", "registry-submit-secret")
    session_id = game_session.create("unknown_submit_user", "unknown_game", 2, {"questions": []})
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    token = create_token("unknown_submit_user", "elder", "registry-submit-secret")
    response = client.post(
        "/api/game/submit",
        json={"session_id": session_id, "answers": [], "duration_sec": 0, "abandoned": False},
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "未知题型"


def test_old_games_keep_fixed_seed_contract(factory):
    random.seed(SEED)
    memory_runs = []
    for _ in range(3):
        start = _start(factory, "contract_hash_mb", "memory_box")
        quizzes = start["items"]["quizzes"]
        answers = [{"index": i, "value": q["appeared"]} for i, q in enumerate(quizzes)]
        result = _submit(factory, start["session_id"], answers)
        memory_runs.append(
            {
                "items": start["items"],
                "submit": {
                    key: result[key]
                    for key in ("correct", "total", "accuracy", "next_difficulty", "summary_text")
                },
            }
        )

    bank = json.loads((DATA_DIR / "category_sort.json").read_text(encoding="utf-8"))
    answer_by_id = {group["id"]: group["answer"] for groups in bank.values() for group in groups}
    random.seed(SEED)
    category_runs = []
    for _ in range(3):
        start = _start(factory, "contract_hash_cs", "category_sort")
        questions = start["items"]["questions"]
        answers = [{"index": i, "value": answer_by_id[q["id"]]} for i, q in enumerate(questions)]
        result = _submit(factory, start["session_id"], answers)
        category_runs.append(
            {
                "items": start["items"],
                "submit": {
                    key: result[key]
                    for key in ("correct", "total", "accuracy", "next_difficulty", "summary_text")
                },
            }
        )

    assert _digest(memory_runs) == "b35facf50c3098ebf503de89f62615ed3100e5537575df13201e84aa2600fbed"
    assert _digest(category_runs) == "a1ea5b302356bef2f72a0f486afe17f19ccc43bdb23a6c8d0cad9f575f144fd5"


@pytest.mark.parametrize(
    ("game_type", "expected_total"),
    [("memory_box", 6), ("category_sort", 8), ("number_seq", 8), ("common_sense", 8)],
)
def test_submit_returns_wrong_details(factory, game_type, expected_total):
    start = _start(factory, "details_" + game_type, game_type)
    internal = game_session.get(start["session_id"])["payload"]["questions"]
    if game_type == "memory_box":
        questions = start["items"]["quizzes"]
        wrong = [{"index": i, "value": not q["appeared"]} for i, q in enumerate(questions)]
    else:
        questions = start["items"]["questions"]
        wrong = []
        for i, q in enumerate(questions):
            correct = internal[i]["correct_text"]
            if game_type == "number_seq":
                value = str(int(correct[0]) % 9 + 1) + correct[1:]
            else:
                value = next(option for option in q["options"] if option != correct)
            wrong.append({"index": i, "value": value})

    result = _submit(factory, start["session_id"], wrong)
    assert result["total"] == expected_total
    assert result["correct"] == 0
    assert len(result["details"]) == expected_total
    assert all(detail["correct"] is False for detail in result["details"])
    assert all(detail["correct_text"] for detail in result["details"])
    assert all(detail["explanation"] for detail in result["details"])


def test_correct_details_have_blank_explanation(factory):
    start = _start(factory, "details_correct", "category_sort")
    internal = game_session.get(start["session_id"])["payload"]["questions"]
    answers = [
        {"index": i, "value": question["correct_text"]}
        for i, question in enumerate(internal)
    ]
    result = _submit(factory, start["session_id"], answers)
    assert all(detail["correct"] is True for detail in result["details"])
    assert all(detail["explanation"] == "" for detail in result["details"])


@pytest.mark.parametrize("game_type", ["number_seq", "common_sense"])
def test_new_bank_has_fifteen_questions_per_level_and_explanations(game_type):
    bank = json.loads((DATA_DIR / f"{game_type}.json").read_text(encoding="utf-8"))
    for level in ("low", "mid", "high"):
        assert len(bank[level]) >= 15
        for question in bank[level]:
            assert question["explanation"].strip()
            assert not any(word in question["explanation"] for word in FORBIDDEN_EXPLANATION_WORDS)


@pytest.mark.parametrize("game_type", ["memory_box", "category_sort"])
def test_old_bank_questions_have_safe_explanations(game_type):
    bank = json.loads((DATA_DIR / f"{game_type}.json").read_text(encoding="utf-8"))
    for groups in bank.values():
        for group in groups:
            questions = group["quizzes"] if game_type == "memory_box" else [group]
            for question in questions:
                assert question["explanation"].strip()
                assert not any(
                    word in question["explanation"] for word in FORBIDDEN_EXPLANATION_WORDS
                )


def test_number_seq_items_and_judging(factory):
    module = GAME_REGISTRY["number_seq"]
    for difficulty, digits in ((1, 3), (2, 4), (3, 5)):
        generated = module.generate(difficulty, module.QUESTION_COUNT[difficulty], f"number_{difficulty}")
        questions = generated["items"]["questions"]
        assert len(questions) == module.QUESTION_COUNT[difficulty]
        for question in questions:
            assert question["show_ms"] == 3000
            assert len(question["options"]) == 4
            assert all(len(option) == digits for option in question["options"])
            assert "answer" not in question
            assert "explanation" not in question


@pytest.mark.parametrize("game_type", ["number_seq", "common_sense"])
def test_new_game_engine_question_counts_by_level(factory, game_type):
    middle = _start(factory, "level_mid_" + game_type, game_type)
    assert middle["difficulty"] == 2
    assert len(middle["items"]["questions"]) == 8

    low_user = "level_low_" + game_type
    _add_records(factory, low_user, game_type, 1, 6, 0)
    low = _start(factory, low_user, game_type)
    assert low["difficulty"] == 1
    assert len(low["items"]["questions"]) == 6

    high_user = "level_high_" + game_type
    _add_records(factory, high_user, game_type, 3, 10, 10)
    high = _start(factory, high_user, game_type)
    assert high["difficulty"] == 3
    assert len(high["items"]["questions"]) == 10


def test_common_sense_items_do_not_leak_answers(factory):
    start = _start(factory, "common_items", "common_sense")
    for question in start["items"]["questions"]:
        assert question["question"]
        assert 2 <= len(question["options"]) <= 3
        assert "answer" not in question
        assert "explanation" not in question


@pytest.mark.parametrize(
    ("text", "game_type"),
    [
        ("咱们记东西吧", "memory_box"),
        ("把东西分一分", "category_sort"),
        ("我想玩记数字", "number_seq"),
        ("说个生活常识题", "common_sense"),
    ],
)
def test_chat_can_route_to_each_game(text, game_type):
    from app.agent.nodes.plan import _resolve_game_type

    assert _resolve_game_type(text, "route_user", None) == game_type


def test_start_api_accepts_difficulty_hint(factory, monkeypatch):
    """接口层接受可选 difficulty，非法档位交给 pydantic 拦成 422。"""
    import app.api.games as games_api

    monkeypatch.setattr(games_api, "SessionLocal", factory)
    monkeypatch.setattr(config, "AUTH_SECRET", "registry-hint-secret")
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    token = create_token("hint_user", "elder", "registry-hint-secret")

    ok = client.post(
        "/api/game/start",
        json={"game_type": "memory_box", "difficulty": 1},
        headers={"Authorization": "Bearer " + token},
    )
    assert ok.status_code == 200
    assert ok.json()["difficulty"] == 1

    bad = client.post(
        "/api/game/start",
        json={"game_type": "memory_box", "difficulty": 9},
        headers={"Authorization": "Bearer " + token},
    )
    assert bad.status_code == 422
