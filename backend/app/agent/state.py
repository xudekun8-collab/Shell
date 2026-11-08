"""智能体流程的 State 定义。"""
from typing import TypedDict


class State(TypedDict, total=False):
    user_id: str
    thread_id: str
    raw_input: str
    input_type: str
    intent: str
    emotion: str
    emotion_score: float
    task_context: dict | None
    available_actions: list[str]
    memories: list
    recent_dialogue: list[str]
    conversation_summary: str | None
    open_items: list
    profile: dict | None
    plan: dict
    reply_text: str
    effects: list
