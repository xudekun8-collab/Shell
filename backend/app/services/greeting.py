"""按时间主动问候：纯规则拼装，不调大模型。"""
from datetime import datetime, time

from app.db.models import Conversation, InteractionEvent


def period_of(now: datetime) -> str:
    """按本地时间判定时段，边界含左端点、不含右端点。"""
    t = now.time()
    if time(5, 0) <= t < time(11, 0):
        return "morning"
    if time(11, 0) <= t < time(14, 0):
        return "noon"
    if time(14, 0) <= t < time(18, 0):
        return "afternoon"
    if time(18, 0) <= t < time(22, 0):
        return "evening"
    return "night"


def build_greeting(profile, now: datetime | None = None) -> dict:
    """根据画像与当前时间拼一句问候。profile 为 None 时用「您」。"""
    if now is None:
        now = datetime.now()
    period = period_of(now)
    name = "您"
    if profile is not None and profile.nickname:
        name = profile.nickname

    if period == "morning":
        text = f"{name}，早上好。昨晚睡得踏实不踏实？"
    elif period == "noon":
        text = f"{name}，该吃饭了，今天想吃点啥？"
    elif period == "afternoon":
        text = f"{name}，下午这会儿闲着没？陪我说说话吧。"
    elif period == "evening":
        text = f"{name}，今天有啥高兴的事儿？"
    else:
        text = f"{name}，夜深了，早点歇着，明天我再来陪您。"

    if period == "evening" and profile is not None and profile.interests:
        text += f"您上次说喜欢{profile.interests[0]}，还惦记着吗？"

    return {"greeting": text, "period": period}


def record_greeting(db, user_id: str, thread_id: str, greeting_text: str) -> None:
    """把主动问候作为一条助手轮写入上下文来源。

    问候不是用户输入：raw_input 留空、input_type 记 greeting、不计 latency、
    不调大模型。recent_turns 从 interaction_events 组装上下文，只有写这里，
    下一轮 /api/chat 的模型才看得见自己刚问过什么。

    问候写入 interaction_events 供 recent_turns 读取，但不计入 msg_count，
    避免提前触发会话压缩。
    """
    conv = db.get(Conversation, thread_id)
    if conv is None:
        conv = Conversation(id=thread_id, user_id=user_id)
        db.add(conv)
    else:
        conv.user_id = user_id
    db.add(
        InteractionEvent(
            user_id=user_id,
            thread_id=thread_id,
            input_type="greeting",
            raw_input="",
            perceived={},
            action="reply",
            reason="主动问候",
            reply_text=greeting_text,
            latency_ms=0,
        )
    )
    db.commit()
