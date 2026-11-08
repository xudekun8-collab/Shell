"""输出每条 query 的目标记忆与 top3 干扰记忆的分数分解，写 data/score_breakdown.md。"""
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.memory.scoring import score_breakdown, score_memory
from scripts.seed_demo import seed_memories

LABELS_PATH = Path("data/memory_labels.json")
OUT_PATH = Path("data/score_breakdown.md")


def load_labels() -> list[dict]:
    data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    return [d for d in data if d.get("label") is not None]


def main() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    memories = seed_memories(factory)
    by_id = {m["memory_id"]: m for m in memories}
    labeled = load_labels()
    lines = ["# 记忆召回分数分解", "", "说明每条 query 的目标记忆为什么排在当前名次，供论文附录使用。", ""]
    for item in labeled:
        query = item["query"]
        label = int(item["label"])
        target = by_id[label]
        ranked = sorted(
            memories,
            key=lambda m: score_memory(query, m["content"], m["importance"], m["occurred_at"], m["layer"]),
            reverse=True,
        )
        rank = next((i for i, m in enumerate(ranked, start=1) if m["memory_id"] == label), None)
        lines.append(f"## query：{query}（目标记忆 #{label}，排名 {rank}）")
        lines.append("")
        lines.append(f"目标记忆：{target['content']}")
        lines.append("")
        tb = score_breakdown(query, target["content"], target["importance"], target["occurred_at"], target["layer"])
        lines.append(f"- 目标分数分解：overlap={tb['overlap']}，time={tb['time']}，importance={tb['importance']}，type={tb['type']}，total={tb['total']}")
        lines.append("")
        lines.append("Top3 干扰记忆（不含目标）：")
        lines.append("")
        lines.append("| 排名 | 记忆内容 | overlap | time | importance | type | total |")
        lines.append("|---|---|---|---|---|---|---|")
        shown = 0
        for i, m in enumerate(ranked, start=1):
            if m["memory_id"] == label:
                continue
            b = score_breakdown(query, m["content"], m["importance"], m["occurred_at"], m["layer"])
            lines.append(f"| {i} | {m['content'][:30]} | {b['overlap']} | {b['time']} | {b['importance']} | {b['type']} | {b['total']} |")
            shown += 1
            if shown >= 3:
                break
        lines.append("")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写入 {OUT_PATH}，覆盖 {len(labeled)} 条 query")


if __name__ == "__main__":
    main()
