"""BM25 与批量召回打分测试。"""
import math

import pytest

from app.memory.bm25 import build_index, score_all, strip_time_words
from app.memory.scoring import score_memory
from app.memory.store import score_candidates


def test_bm25_manual_idf_and_zero_score():
    index = build_index(["aa", "aa", "b"])
    scores = score_all("aa", index)
    expected = math.log(1.6)
    assert scores[0] == pytest.approx(expected)
    assert scores[1] == pytest.approx(expected)
    assert scores[2] == 0.0
    assert score_all("完全不存在", index) == [0.0, 0.0, 0.0]


def test_score_candidates_legacy_and_modes():
    memories = [
        {
            "memory_id": 1,
            "content": "我孙女来看我",
            "importance": 5,
            "occurred_at": None,
            "layer": "event",
        },
        {
            "memory_id": 2,
            "content": "我孙女打电话说周末来",
            "importance": 4,
            "occurred_at": None,
            "layer": "event",
        },
        {
            "memory_id": 3,
            "content": "昨天去买菜",
            "importance": 3,
            "occurred_at": None,
            "layer": "event",
        },
    ]
    query = "我孙女打电话"
    legacy = score_candidates(query, memories, mode="legacy")
    bm25 = score_candidates(query, memories, mode="bm25")
    hybrid = score_candidates(query, memories, mode="hybrid")
    assert [m["memory_id"] for m, _, _ in legacy] == [2, 1]
    assert [m["memory_id"] for m, _, _ in bm25] == [2, 1]
    assert [m["memory_id"] for m, _, _ in hybrid] == [2, 1]
    assert all(isinstance(score, float) for _, score, _ in bm25 + hybrid)
    expected_legacy = score_memory(query, memories[1]["content"], 4, None, "event")
    assert legacy[0][1] == pytest.approx(expected_legacy)
    assert bm25[0][1] != pytest.approx(legacy[0][1])


def test_score_candidates_rejects_unknown_mode():
    with pytest.raises(ValueError, match="未知召回模式"):
        score_candidates("孙女", [], mode="unknown")


def test_strip_time_words_keeps_semantic_part():
    assert strip_time_words("我昨天哪里不舒服") == "我哪里不舒服"
    assert strip_time_words("上周三去公园") == "去公园"
    assert strip_time_words("昨天") == ""


def test_time_only_query_has_zero_bm25():
    index = build_index(["昨天去看病", "我哪里不舒服"])
    assert score_all(strip_time_words("昨天"), index) == [0.0, 0.0]


def test_legacy_short_circuits_bm25(monkeypatch):
    import app.memory.store as store_mod

    def fail(*args, **kwargs):
        raise AssertionError("legacy 不应构建 BM25")

    monkeypatch.setattr(store_mod, "build_index", fail)
    memories = [
        {
            "memory_id": 1,
            "content": "我孙女来看我",
            "importance": 5,
            "occurred_at": None,
            "layer": "event",
        }
    ]
    assert score_candidates("我孙女", memories, mode="legacy")


def test_v2_uses_stripped_query_only(monkeypatch):
    import app.memory.store as store_mod

    seen = []
    original = store_mod.score_all

    def spy(query, index):
        seen.append(query)
        return original(query, index)

    monkeypatch.setattr(store_mod, "score_all", spy)
    memories = [
        {
            "memory_id": 1,
            "content": "我昨天哪里不舒服",
            "importance": 5,
            "occurred_at": None,
            "layer": "event",
        }
    ]
    score_candidates("我昨天哪里不舒服", memories, mode="bm25")
    score_candidates("我昨天哪里不舒服", memories, mode="hybrid_v2")
    score_candidates("我昨天哪里不舒服", memories, mode="hybrid_v3")
    assert "昨天" in seen[0]
    assert "昨天" not in seen[1]
    assert "昨天" not in seen[2]


def test_hybrid_v4_strips_jaccard_query(monkeypatch):
    import app.memory.store as store_mod

    seen = []
    original = store_mod.overlap_score

    def spy(query, content):
        seen.append(query)
        return original(query, content)

    monkeypatch.setattr(store_mod, "overlap_score", spy)
    memories = [
        {
            "memory_id": 1,
            "content": "我昨天蒸了馒头",
            "importance": 3,
            "occurred_at": None,
            "layer": "event",
        }
    ]
    score_candidates("我昨天哪里不舒服", memories, mode="hybrid_v3")
    assert seen[-1] == "我昨天哪里不舒服"
    seen.clear()
    score_candidates("我昨天哪里不舒服", memories, mode="hybrid_v4")
    assert seen[-1] == "我哪里不舒服"


def test_hybrid_v4_zeroes_fall_back_to_importance():
    memories = [
        {
            "memory_id": 1,
            "content": "昨天蒸了一锅馒头",
            "importance": 3,
            "occurred_at": None,
            "layer": "event",
        },
        {
            "memory_id": 2,
            "content": "昨天去诊所配了点降压药",
            "importance": 5,
            "occurred_at": None,
            "layer": "event",
        },
    ]
    ranked = score_candidates(
        "我昨天哪里不舒服",
        memories,
        mode="hybrid_v4",
        tie_break=False,
    )
    assert [memory["memory_id"] for memory, _, _ in ranked] == [2, 1]
    assert ranked[0][1] == pytest.approx(0.12)
    assert ranked[1][1] == pytest.approx(0.104)
