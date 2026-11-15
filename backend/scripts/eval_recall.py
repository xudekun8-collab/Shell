"""召回消融实验：4 组权重下计算 Recall@3、MRR、命中条数；--hard 额外输出困难子集。"""
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.memory.scoring import WEIGHTS, parse_time_offset
from app.memory.store import score_candidates
from scripts.seed_demo import seed_memories

LABELS_PATH = Path("data/memory_labels.json")
RESULT_PATH = Path("data/eval_result.json")
LEGACY_BACKUP_PATH = Path("data/eval_result.legacy_backup.json")

GROUPS = {
    "默认": {"weights": {}, "filter_time": False},
    "去掉重要性项": {"weights": {"importance": 0.0}, "filter_time": False},
    "去掉类型项": {"weights": {"type": 0.0}, "filter_time": False},
    "时间预过滤": {"weights": {}, "filter_time": True},
}

# 困难 query：这些 query 的目标记忆存在同主题的近义干扰记忆（见 seed_demo.py 末尾 20 条）。
# 索引是 QUERIES 列表里的 1 基位置，写死在此处便于复现。
HARD_QUERY_INDEXES = [1, 2, 5, 6, 7, 8, 9, 14, 18, 19, 20, 22, 25, 27, 28, 29, 30]

# 时间检验子集：QUERIES 末尾追加的 6 条带时间词的配对 query（1 基位置 31-36）。
TIME_QUERY_INDEXES = [31, 32, 33, 34, 35, 36]


def load_data() -> list[dict]:
    if not LABELS_PATH.exists():
        print(f"未找到 {LABELS_PATH}，请先运行 scripts/make_label_json.py")
        return []
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def evaluate(
    queries: list[dict],
    memories: list[dict],
    weights_override: dict,
    filter_time: bool = False,
    mode: str = "legacy",
) -> dict:
    hits = 0
    rr_sum = 0.0
    for item in queries:
        query = item["query"]
        label = int(item["label"])
        ranked = score_candidates(
            query,
            memories,
            weights=weights_override,
            filter_time=filter_time,
            mode=mode,
            # 三模式统一保持旧实验的纯分数排序，只比较打分方式，不混入 tie-break 差异。
            tie_break=False,
        )
        rank = next((i for i, (m, _, _) in enumerate(ranked, start=1) if m["memory_id"] == label), None)
        if rank is not None and rank <= 3:
            hits += 1
        if rank is not None:
            rr_sum += 1.0 / rank
    total = len(queries)
    return {
        "recall_at_3": round(hits / total, 4) if total else 0.0,
        "mrr": round(rr_sum / total, 4) if total else 0.0,
        "hits": hits,
        "total": total,
    }


def run_groups(queries: list[dict], memories: list[dict]) -> dict:
    return {
        name: evaluate(queries, memories, cfg["weights"], cfg["filter_time"], mode="legacy")
        for name, cfg in GROUPS.items()
    }


def print_table(title: str, results: dict) -> None:
    print(f"\n## {title}")
    print("| 权重组 | Recall@3 | MRR | 命中条数 | 总数 |")
    print("|---|---|---|---|---|")
    for name, r in results.items():
        print(f"| {name} | {r['recall_at_3']} | {r['mrr']} | {r['hits']} | {r['total']} |")


def main() -> None:
    if not LEGACY_BACKUP_PATH.exists():
        shutil.copy2(RESULT_PATH, LEGACY_BACKUP_PATH)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    memories = seed_memories(factory)
    data = load_data()
    parsable = sum(1 for d in data if parse_time_offset(d["query"]) is not None)
    print(f"可解析时间词：{parsable}/{len(data)}")
    labeled_all = [d for d in data if d.get("label") is not None]
    skipped = len(data) - len(labeled_all)
    if skipped:
        print(f"跳过 {skipped} 条 label 为空的 query")
    if len(labeled_all) < 20:
        print(f"提示：已标注 {len(labeled_all)} 条，少于 20 条，请先完成人工标注")

    results_all = run_groups(labeled_all, memories)
    print_table("全部 query", results_all)

    payload = {"weights": WEIGHTS, "annotated": len(labeled_all), "results": results_all}
    bm25_all = evaluate(labeled_all, memories, {}, mode="bm25")
    hybrid_all = evaluate(labeled_all, memories, {}, mode="hybrid")
    bm25_v2_all = evaluate(labeled_all, memories, {}, mode="bm25_v2")
    hybrid_v2_all = evaluate(labeled_all, memories, {}, mode="hybrid_v2")
    hybrid_v3_all = evaluate(labeled_all, memories, {}, mode="hybrid_v3")
    hybrid_v4_all = evaluate(labeled_all, memories, {}, mode="hybrid_v4")
    print_table("全部 query / BM25", {"BM25": bm25_all})
    print_table("全部 query / Hybrid", {"Hybrid": hybrid_all})
    print_table("全部 query / BM25 v2", {"BM25 v2": bm25_v2_all})
    print_table("全部 query / Hybrid v2", {"Hybrid v2": hybrid_v2_all})
    print_table("全部 query / Hybrid v3", {"Hybrid v3": hybrid_v3_all})
    print_table("全部 query / Hybrid v4", {"Hybrid v4": hybrid_v4_all})
    payload["results_bm25"] = bm25_all
    payload["results_hybrid"] = hybrid_all
    payload["results_bm25_v2"] = bm25_v2_all
    payload["results_hybrid_v2"] = hybrid_v2_all
    payload["results_hybrid_v3"] = hybrid_v3_all
    payload["results_hybrid_v4"] = hybrid_v4_all

    if "--hard" in sys.argv:
        hard_labeled = [d for i, d in enumerate(data, 1) if i in HARD_QUERY_INDEXES and d.get("label") is not None]
        results_hard = run_groups(hard_labeled, memories)
        bm25_hard = evaluate(hard_labeled, memories, {}, mode="bm25")
        hybrid_hard = evaluate(hard_labeled, memories, {}, mode="hybrid")
        bm25_v2_hard = evaluate(hard_labeled, memories, {}, mode="bm25_v2")
        hybrid_v2_hard = evaluate(hard_labeled, memories, {}, mode="hybrid_v2")
        hybrid_v3_hard = evaluate(hard_labeled, memories, {}, mode="hybrid_v3")
        hybrid_v4_hard = evaluate(hard_labeled, memories, {}, mode="hybrid_v4")
        print_table("--hard 子集", results_hard)
        print_table("--hard 子集 / BM25", {"BM25": bm25_hard})
        print_table("--hard 子集 / Hybrid", {"Hybrid": hybrid_hard})
        print_table("--hard 子集 / BM25 v2", {"BM25 v2": bm25_v2_hard})
        print_table("--hard 子集 / Hybrid v2", {"Hybrid v2": hybrid_v2_hard})
        print_table("--hard 子集 / Hybrid v3", {"Hybrid v3": hybrid_v3_hard})
        print_table("--hard 子集 / Hybrid v4", {"Hybrid v4": hybrid_v4_hard})
        payload["results_hard"] = results_hard
        payload["results_bm25_hard"] = bm25_hard
        payload["results_hybrid_hard"] = hybrid_hard
        payload["results_bm25_v2_hard"] = bm25_v2_hard
        payload["results_hybrid_v2_hard"] = hybrid_v2_hard
        payload["results_hybrid_v3_hard"] = hybrid_v3_hard
        payload["results_hybrid_v4_hard"] = hybrid_v4_hard

    if "--time" in sys.argv:
        time_labeled = [d for i, d in enumerate(data, 1) if i in TIME_QUERY_INDEXES and d.get("label") is not None]
        results_time = run_groups(time_labeled, memories)
        bm25_time = evaluate(time_labeled, memories, {}, mode="bm25")
        hybrid_time = evaluate(time_labeled, memories, {}, mode="hybrid")
        bm25_v2_time = evaluate(time_labeled, memories, {}, mode="bm25_v2")
        hybrid_v2_time = evaluate(time_labeled, memories, {}, mode="hybrid_v2")
        hybrid_v3_time = evaluate(time_labeled, memories, {}, mode="hybrid_v3")
        hybrid_v4_time = evaluate(time_labeled, memories, {}, mode="hybrid_v4")
        print_table("--time 子集", results_time)
        print_table("--time 子集 / BM25", {"BM25": bm25_time})
        print_table("--time 子集 / Hybrid", {"Hybrid": hybrid_time})
        print_table("--time 子集 / BM25 v2", {"BM25 v2": bm25_v2_time})
        print_table("--time 子集 / Hybrid v2", {"Hybrid v2": hybrid_v2_time})
        print_table("--time 子集 / Hybrid v3", {"Hybrid v3": hybrid_v3_time})
        print_table("--time 子集 / Hybrid v4", {"Hybrid v4": hybrid_v4_time})
        payload["results_time"] = results_time
        payload["results_bm25_time"] = bm25_time
        payload["results_hybrid_time"] = hybrid_time
        payload["results_bm25_v2_time"] = bm25_v2_time
        payload["results_hybrid_v2_time"] = hybrid_v2_time
        payload["results_hybrid_v3_time"] = hybrid_v3_time
        payload["results_hybrid_v4_time"] = hybrid_v4_time

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {RESULT_PATH}")


if __name__ == "__main__":
    main()
