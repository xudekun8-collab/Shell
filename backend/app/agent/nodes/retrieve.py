"""记忆检索节点：召回事件记忆，读取画像与会话摘要。"""
from app.agent.actions import ALL_ACTIONS
from app.db.models import Conversation, Profile
from app.memory.store import recall


def make_retrieve(session_factory):
    def retrieve(state: dict) -> dict:
        profile = None
        conversation_summary = None
        open_items = []
        user_id = state.get("user_id")
        thread_id = state.get("thread_id")
        with session_factory() as session:
            if user_id:
                p = session.get(Profile, user_id)
                if p:
                    profile = {
                        "nickname": p.nickname,
                        "interests": p.interests or [],
                        "taboos": p.taboos or [],
                        "wake_time": p.wake_time,
                        "sleep_time": p.sleep_time,
                    }
            if thread_id:
                conv = session.get(Conversation, thread_id)
                if conv:
                    conversation_summary = conv.summary
                    open_items = conv.open_items or []
        memories = recall(user_id, state.get("raw_input") or "", top_k=3, session_factory=session_factory)
        formatted = [f"{m.get('occurred_at') or '今天'} {m['content']}" for m in memories]
        return {
            "memories": formatted,
            "profile": profile,
            "conversation_summary": conversation_summary,
            "open_items": open_items,
            "available_actions": list(ALL_ACTIONS),
        }

    return retrieve
