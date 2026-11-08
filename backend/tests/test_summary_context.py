"""会话摘要与 open_items 进入上下文的测试。"""
from app.llm.prompts import build_system_prompt


def _base_state() -> dict:
    return {"available_actions": ["reply", "start_game", "start_assessment", "suggest_rest", "remind", "end"]}


def test_summary_shows_in_prompt():
    state = _base_state()
    state["conversation_summary"] = "老人下周三要复查眼睛"
    prompt = build_system_prompt(state)
    assert "之前聊过的摘要" in prompt
    assert "老人下周三要复查眼睛" in prompt


def test_empty_summary_omits_section():
    state = _base_state()
    state["conversation_summary"] = None
    prompt = build_system_prompt(state)
    assert "之前聊过的摘要" not in prompt
    assert "None" not in prompt


def test_open_items_show_in_prompt():
    state = _base_state()
    state["conversation_summary"] = ""
    state["open_items"] = ["下周三复查眼睛", "买降压药"]
    prompt = build_system_prompt(state)
    assert "还没办完的事" in prompt
    assert "下周三复查眼睛" in prompt
    assert "买降压药" in prompt


def test_prompt_length_bounded():
    state = _base_state()
    state["profile"] = {"nickname": "张阿姨", "interests": ["黄梅戏", "养花"], "taboos": ["不要提去世的老伴"]}
    state["recent_dialogue"] = ["老人：今天天气不错／我：我听着呢"] * 6
    state["memories"] = ["2026-10-31 我孙女上周末来看我了，带了点心"] * 3
    state["conversation_summary"] = "老人说下周三要去医院复查眼睛，" * 5
    state["open_items"] = ["下周三复查眼睛"]
    prompt = build_system_prompt(state)
    assert len(prompt) <= 1200
