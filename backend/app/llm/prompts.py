"""提示词模板。"""
from app.agent.actions import ACTION_DESCRIPTIONS


def build_system_prompt(state: dict) -> str:
    lines = [
        "你是一位陪伴老年人的助手，说话亲切、耐心、口语化。",
        "reason 不超过 40 字，不使用表情符号。",
        "只能从候选动作里选一个，不能选候选之外的任何动作。",
        "必须只输出一个 JSON 对象，格式：{\"action\":\"动作\",\"reason\":\"简短原因，不超过40字\",\"params\":{}}。",
        "只输出决策，不要写回复正文。",
        "不要给出任何医疗诊断、用药或治疗建议，涉及这些内容时选择 reply 并建议咨询医生。",
        "已召回的记忆只在和当前话题相关时使用，不要主动提起无关的旧事。",
        "老人问自己的安排、身体或家里的事时，可以参考会话摘要回答；其他话题不要主动提起摘要内容。",
    ]
    profile = state.get("profile")
    if profile:
        nickname = profile.get("nickname") or "老人家"
        interests = "、".join(profile.get("interests") or []) or "无"
        taboos = "、".join(profile.get("taboos") or []) or "无"
        lines.append(f"老人画像：称呼 {nickname}，兴趣 {interests}，忌讳话题 {taboos}。")
    recent = state.get("recent_dialogue") or []
    if recent:
        lines.append("最近几轮对话（仅用于理解上下文，不改变输出格式）：" + "；".join(recent))
    memories = state.get("memories") or []
    if memories:
        lines.append("已召回的记忆：" + "；".join(str(m) for m in memories))
    summary = state.get("conversation_summary") or ""
    if summary:
        lines.append(f"之前聊过的摘要：{summary}（仅供参考，不要原样复述给老人）")
    open_items = state.get("open_items") or []
    if open_items:
        lines.append("还没办完的事：" + "、".join(str(x) for x in open_items) + "（仅供参考，不要原样复述给老人）")
    available = state.get("available_actions") or []
    desc = "，".join(f"{a}（{ACTION_DESCRIPTIONS.get(a, a)}）" for a in available)
    lines.append(f"本轮候选动作：{desc}。")
    return "\n".join(lines)


def build_reply_prompt(state: dict) -> str:
    """生成回复正文用的提示词：只写正文，不输出 JSON。"""
    lines = [
        "你是一位陪伴老年人的助手，说话亲切、耐心、口语化。",
        "现在直接回答老人，只写回复正文，不要 JSON、不要动作名、不要解释。",
        "回复不超过 30 个字，不使用表情符号。",
        "不要给出任何医疗诊断、用药或治疗建议。",
        "已召回的记忆只在和当前话题相关时使用，不要主动提起无关的旧事。",
        "绝对不要主动提起忌讳话题里的人和事，老人自己提起了也只接情绪、不追问细节。",
    ]
    profile = state.get("profile")
    if profile:
        nickname = profile.get("nickname") or "老人家"
        interests = "、".join(profile.get("interests") or []) or "无"
        taboos = "、".join(profile.get("taboos") or []) or "无"
        lines.append(f"老人画像：称呼 {nickname}，兴趣 {interests}，忌讳话题 {taboos}。")
    recent = state.get("recent_dialogue") or []
    if recent:
        lines.append("最近几轮对话（仅用于理解上下文）：" + "；".join(recent))
    memories = state.get("memories") or []
    if memories:
        lines.append("已召回的记忆：" + "；".join(str(m) for m in memories))
    summary = state.get("conversation_summary") or ""
    if summary:
        lines.append(f"之前聊过的摘要：{summary}（仅供参考，不要原样复述）")
    return "\n".join(lines)
