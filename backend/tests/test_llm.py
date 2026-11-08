"""LLM 客户端与解析逻辑测试，不发网络。"""
import pytest

from app.llm.client import OpenAIClient, UnsupportedResponseFormat, _chat_url, _extract_json
from app.llm.schemas import PlanParseError, parse_plan


def test_chat_url_joins_v1_once():
    assert _chat_url("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert _chat_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1/chat/completions"


def test_extract_json_plain_and_wrapped():
    assert _extract_json('{"action":"reply"}') == {"action": "reply"}
    assert _extract_json('好的，如下：{"action":"end"} 谢谢') == {"action": "end"}


def test_extract_json_invalid_raises():
    with pytest.raises(PlanParseError):
        _extract_json("没有 JSON")


def test_parse_plan_valid_and_invalid():
    plan = parse_plan({"action": "reply", "reason": "闲聊", "params": {}})
    assert plan.action == "reply"
    with pytest.raises(PlanParseError):
        parse_plan({"action": "fly", "reason": "", "params": {}})


def test_openai_client_falls_back_to_no_response_format(monkeypatch):
    calls = []

    def fake_chat(messages, response_format):
        calls.append(response_format)
        if response_format is not None:
            raise UnsupportedResponseFormat()
        return '{"action":"reply","reason":"闲聊","params":{"reply_text":"好呀"}}'

    client = OpenAIClient(base_url="https://api.deepseek.com", api_key="k", model="m", timeout=5)
    monkeypatch.setattr(client, "_chat", fake_chat)
    plan = client.plan({"raw_input": "你好"})
    assert plan["action"] == "reply"
    assert plan["params"]["reply_text"] == "好呀"
    assert calls == [{"type": "json_object"}, None]


def test_extract_json_from_markdown_fence():
    content = '```json\n{"action":"end","reason":"结束","params":{}}\n```'
    assert _extract_json(content) == {"action": "end", "reason": "结束", "params": {}}
