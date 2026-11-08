"""生成召回标注模板：40 条底料记忆 + 30 条 query，label 留空待人工填。"""
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from scripts.seed_demo import seed_memories

QUERIES = [
    "我孙女啥时候来看我的",
    "我儿子昨天打电话说了什么",
    "我老伴上周陪我干啥了",
    "我女儿前天来帮我干啥了",
    "我昨天哪里不舒服",
    "我上周去医院复查了什么",
    "我前天腿怎么了",
    "我上周感冒吃了几天药",
    "我昨天配了什么药",
    "我下个月有什么大事",
    "上周过什么节了",
    "上个月中秋怎么过的",
    "昨天是谁的生日",
    "我上周体检结果怎么样",
    "前天社区打电话通知什么",
    "我上周整理了什么东西",
    "我昨天收到了什么",
    "我昨天买了什么菜",
    "我前天和谁下棋了",
    "我上周去理发了吗",
    "我前天早上遇到了谁",
    "我上周把花怎么了",
    "我昨天蒸了什么",
    "我前天去银行干啥了",
    "我上周三参加了什么活动",
    "我昨天买了什么水果",
    "我上周借了什么书",
    "我前天约了谁包饺子",
    "我前天去公园干啥了",
    "我上周配了什么眼镜",
    "我昨天量的血压多少",
    "我昨天吃了几片降压药",
    "我昨天买的什么菜",
    "我昨天和谁通了电话",
    "我昨天浇花了吗",
    "我昨天中午吃的什么",
]


def main() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    memories = seed_memories(factory)
    print("底料记忆（供人工标注时对照 memory_id）：")
    for m in memories:
        print(f"{m['memory_id']}\t{m['content']}\timportance={m['importance']}")
    template = [{"query": q, "label": None} for q in QUERIES]
    out = Path("data/memory_labels.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out}，共 {len(template)} 条 query，label 留空待人工标注")


if __name__ == "__main__":
    main()
