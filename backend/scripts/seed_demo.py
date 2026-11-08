"""演示数据：造事件/会话记忆做消融实验底料。"""
import argparse
from datetime import date, timedelta

from sqlalchemy import delete, func, select

from app.db.models import Conversation, InteractionEvent, Memory, Profile, TrainingRecord

SEED_MEMORIES = [
    ("我孙女上周末来看我，带了一盒点心", 5, 7),
    ("儿子昨天打电话说周末要回家吃饭", 5, 1),
    ("老伴上周陪我去公园散步", 5, 7),
    ("女儿前天来看我，帮我收拾了屋子", 5, 2),
    ("昨天头有点晕，量了血压有点高", 5, 1),
    ("上周去医院复查眼睛，医生说没问题", 5, 7),
    ("前天腿有点疼，贴了膏药好多了", 5, 2),
    ("上周感冒了，吃了三天药才好", 5, 7),
    ("昨天去诊所配了点降压药", 5, 1),
    ("下个月初八是我八十大寿，孩子们要回来", 4, 0),
    ("上周过重阳节，社区给送了慰问品", 4, 7),
    ("上个月中秋节，孩子们回来吃了团圆饭", 4, 30),
    ("昨天是孙女的生日，我给她包了红包", 4, 1),
    ("上周去体检，血压血糖都正常", 4, 7),
    ("前天社区来电话通知体检安排", 4, 2),
    ("上周把家里的药盒整理了一遍", 4, 7),
    ("昨天收到儿子寄来的钙片", 4, 1),
    ("昨天去菜市场买了青菜和豆腐", 3, 1),
    ("前天在楼下和老李下了两盘棋", 3, 2),
    ("上周去理发店剪了头发", 3, 7),
    ("昨天在家看了会儿电视", 3, 1),
    ("前天早上出去遛弯，遇到了王奶奶", 3, 2),
    ("上周把阳台的花都浇了一遍", 3, 7),
    ("昨天蒸了一锅馒头", 3, 1),
    ("前天去银行取了点退休金", 3, 2),
    ("上周三去社区参加了合唱活动", 3, 4),
    ("昨天傍晚在小区门口买了两斤苹果", 3, 1),
    ("上周去图书馆借了两本书", 3, 7),
    ("昨天在阳台上晒了晒被子", 3, 1),
    ("前天和邻居约好下周三一起包饺子", 3, 2),
    ("昨天把旧衣服整理出来准备捐掉", 3, 1),
    ("前天去公园听了一下午戏", 3, 2),
    ("上周买了一盆茉莉花放在窗台", 3, 7),
    ("昨天中午炖了排骨汤", 3, 1),
    ("前天晚上梦见老家的院子了", 3, 2),
    ("上周去配了一副新的老花镜", 3, 7),
    ("昨天和楼上的张姐约了明天下楼遛弯", 3, 1),
    ("前天去称了体重，轻了两斤", 3, 2),
    ("上周看了新闻说这几天要降温", 3, 7),
    ("昨天把冬天的棉衣翻出来晒了晒", 3, 1),
    # 以下 20 条为近义干扰记忆：与上面某条同主题但时间更早、importance 更低，给消融加难度。
    # 顺序必须追加在末尾，前 40 条顺序不变（memory_labels.txt 里的 id 依赖它）。
    ("上个月去医院复查眼睛，医生让继续点眼药", 3, 30),
    ("半年前体检，查出血糖偏高", 3, 180),
    ("上个月头晕过一次，躺了半天才好", 3, 30),
    ("两个月前腿疼，去医院拍过片子", 3, 60),
    ("上个月感冒过一次，咳了十来天", 3, 30),
    ("半年前配过降压药，后来没再吃", 3, 180),
    ("上个月去菜市场买过鱼和排骨", 3, 30),
    ("上个月和老李在楼下下过象棋", 3, 30),
    ("两个月前去理发店剪过头发", 3, 60),
    ("上个月去图书馆借过一本养生书", 3, 30),
    ("上个月在公园听过一场黄梅戏", 3, 30),
    ("半年前配过一副老花镜，度数又涨了", 3, 180),
    ("上上个月孙女也来看过我一次", 3, 45),
    ("上个月儿子也打电话问过身体", 3, 30),
    ("上个月和邻居一起包过一次饺子", 3, 30),
    ("三个月前体检，医生说血压偏高", 3, 90),
    ("两个月前也感冒过，吃了几天药", 3, 60),
    ("两个月前借的书还没看完", 3, 60),
    ("上个月把花都换过一遍土", 3, 30),
    ("上个月参加过一次社区合唱", 3, 30),
    # 以下 12 条为时间检验配对记忆：6 组，内容几乎相同、仅日期不同，importance 统一 3。
    # 每组第一条是“昨天”版、第二条是“上周三”版，occurred_at 分别按 1 天 / 4 天前。
    ("量了血压，高压有点高", 3, 1),
    ("量了血压，医生说还行", 3, 4),
    ("吃了两片降压药", 3, 1),
    ("吃了降压药，感觉有点头晕", 3, 4),
    ("去菜市场买了菠菜", 3, 1),
    ("去菜市场买了豆角", 3, 4),
    ("和孙女通了电话", 3, 1),
    ("和孙女通了电话，她说过年回来", 3, 4),
    ("在阳台浇了花", 3, 1),
    ("在阳台浇了花，还换了土", 3, 4),
    ("中午吃了面条", 3, 1),
    ("中午吃了米饭和青菜", 3, 4),
]

SESSION_MEMORIES = [
    ("老人提到下周三要去医院复查眼睛，记得提前提醒", 4, 1),
    ("老人喜欢黄梅戏，周末常在公园听戏", 3, 3),
    ("老人说孙女在外地上大学，寒假会回来", 4, 2),
    ("老人最近夜里睡不踏实，容易醒", 5, 1),
    ("老人和邻居张姐约好每天早上一起遛弯", 3, 0),
]


def _insert_seeds(session, user_id: str, today: date) -> list[Memory]:
    """在给定会话里插入全部种子记忆，返回按插入顺序的对象列表。"""
    objects = []
    for content, importance, days_ago in SEED_MEMORIES:
        memory = Memory(
            user_id=user_id,
            layer="event",
            content=content,
            importance=importance,
            occurred_at=today - timedelta(days=days_ago),
        )
        session.add(memory)
        objects.append(memory)
    for content, importance, days_ago in SESSION_MEMORIES:
        memory = Memory(
            user_id=user_id,
            layer="session",
            content=content,
            importance=importance,
            occurred_at=today - timedelta(days=days_ago),
        )
        session.add(memory)
        objects.append(memory)
    return objects


def seed_memories(session_factory, user_id: str = "demo_user_1") -> list[dict]:
    """追加全部种子记忆，返回含 memory_id 的列表（不做清理）。"""
    today = date.today()
    with session_factory() as session:
        objects = _insert_seeds(session, user_id, today)
        session.commit()
    return [
        {
            "memory_id": m.id,
            "layer": m.layer,
            "content": m.content,
            "importance": m.importance,
            "occurred_at": m.occurred_at,
        }
        for m in objects
    ]


def reset_demo(session_factory) -> tuple[dict, dict]:
    """只重置 demo_user_1：清空四类数据、重建画像、重灌种子。"""
    user_id = "demo_user_1"
    tables = {
        "memories": Memory,
        "training_records": TrainingRecord,
        "interaction_events": InteractionEvent,
        "conversations": Conversation,
    }
    with session_factory() as session:
        before = {
            name: session.execute(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            ).scalar()
            for name, model in tables.items()
        }
        for model in tables.values():
            session.execute(delete(model).where(model.user_id == user_id))
        profile = session.get(Profile, user_id)
        if profile is None:
            profile = Profile(
                user_id=user_id,
                nickname="张阿姨",
                interests=["黄梅戏", "养花"],
                taboos=["不要提去世的老伴"],
            )
            session.add(profile)
        else:
            profile.nickname = "张阿姨"
            profile.interests = ["黄梅戏", "养花"]
            profile.taboos = ["不要提去世的老伴"]
        _insert_seeds(session, user_id, date.today())
        session.commit()
        after = {
            name: session.execute(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            ).scalar()
            for name, model in tables.items()
        }
    return before, after


def main() -> None:
    parser = argparse.ArgumentParser(description="演示数据脚本")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="只重置 demo_user_1（清空记忆/训练/交互/会话，重建画像并重灌种子）",
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal

    if args.reset:
        before, after = reset_demo(SessionLocal)
        print(
            f"重置前 memories={before['memories']}, "
            f"training_records={before['training_records']}, "
            f"interaction_events={before['interaction_events']}, "
            f"conversations={before['conversations']}"
        )
        print(f"重置后 memories={after['memories']}（应为种子总条数 {len(SEED_MEMORIES) + len(SESSION_MEMORIES)}）")
    else:
        seed_memories(SessionLocal)
        with SessionLocal() as session:
            total = session.execute(
                select(func.count()).select_from(Memory).where(Memory.user_id == "demo_user_1")
            ).scalar()
        print(f"已追加种子记忆，demo_user_1 当前 memories={total}")


if __name__ == "__main__":
    main()
