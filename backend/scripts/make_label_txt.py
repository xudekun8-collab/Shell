"""生成供人工填写的标注文本表：每组给 4 个候选（按字面重合度取，打乱顺序），末尾附全部记忆。"""
import random
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.memory.scoring import overlap_score
from scripts.make_label_template import QUERIES
from scripts.seed_demo import seed_memories

OUT_PATH = Path("data/memory_labels.txt")
SEED = 20261107


def build_txt(memories: list[dict]) -> str:
    rng = random.Random(SEED)
    lines = [
        "# 记忆召回标注表（人工填写，别改其它内容）",
        "# 用法：每组在“我选：”后面填字母 a / b / c / d。四个都不对就填 none。",
        "# 也可以直接填记忆编号，例如 id=23。空着不填的组会被跳过。",
        "# 判断标准只有一条：假设你就是这位老人，问这句话时最想听到哪一条。",
        "",
    ]
    for idx, query in enumerate(QUERIES, start=1):
        scored = sorted(
            memories,
            key=lambda m: overlap_score(query, m["content"]),
            reverse=True,
        )
        top4 = scored[:4]
        rng.shuffle(top4)
        lines.append(f"[{idx:02d}] 查询：{query}")
        for letter, mem in zip("abcd", top4):
            date_str = mem["occurred_at"].isoformat() if mem.get("occurred_at") else "?"
            lines.append(f"     {letter}. id={mem['memory_id']}  [{date_str}]  {mem['content']}")
        lines.append("     我选：____")
        lines.append("")

    lines.append("# " + "=" * 60)
    lines.append("# 全部记忆（上面 4 个候选都不对时，从这里找编号，直接填 id=数字）")
    lines.append("# " + "=" * 60)
    for mem in memories:
        date_str = mem["occurred_at"].isoformat() if mem.get("occurred_at") else "?"
        lines.append(f"{mem['memory_id']}\t[{date_str}]  {mem['content']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    memories = [m for m in seed_memories(factory) if m["layer"] == "event"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_txt(memories), encoding="utf-8")
    print(f"已写入 {OUT_PATH}，共 {len(QUERIES)} 组，记忆 {len(memories)} 条")


if __name__ == "__main__":
    main()
