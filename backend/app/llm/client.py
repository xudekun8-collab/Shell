"""大模型客户端抽象、假模型与 OpenAI 兼容客户端。"""
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Iterator

import httpx

from app import config
from app.agent.actions import ACTION_REPLY, ACTION_START_GAME, ACTION_SUGGEST_REST
from app.llm.prompts import build_reply_prompt, build_system_prompt
from app.llm.schemas import PlanParseError, parse_plan

logger = logging.getLogger("elder_care")


class LLMClient(ABC):
    @abstractmethod
    def plan(self, state: dict) -> dict:
        """根据状态返回 {"action", "reason", "params"}。"""

    @abstractmethod
    def reply(self, state: dict, plan: dict) -> str:
        """根据状态与决策返回回复正文。"""

    @abstractmethod
    def reply_stream(self, state: dict, plan: dict) -> Iterator[str]:
        """逐段产出回复正文。"""

    @abstractmethod
    def summarize(self, dialogue: list[str], previous_summary: str = "") -> dict:
        """把对话压缩成 {"summary", "open_items"}，previous_summary 为已有摘要。"""


class FakeClient(LLMClient):
    """按关键词返回预设动作，不发起任何网络请求。"""

    def plan(self, state: dict) -> dict:
        raw = state.get("raw_input", "") or ""
        memories = state.get("memories") or []
        recent = state.get("recent_dialogue") or []
        summary = state.get("conversation_summary") or ""
        if "游戏" in raw or "玩" in raw:
            return {"action": ACTION_START_GAME, "reason": "用户想玩游戏", "params": {}}
        if "休息" in raw or "累" in raw:
            return {"action": ACTION_SUGGEST_REST, "reason": "用户需要休息", "params": {}}
        if recent and any(k in raw for k in ("刚才说", "刚说了", "说了什么", "上一句", "我之前说")):
            return {"action": ACTION_REPLY, "reason": "参考最近对话回答", "params": {}}
        if summary and any(k in raw for k in ("来着", "干啥", "什么来着", "几号", "几点", "安排", "去哪")):
            return {"action": ACTION_REPLY, "reason": "参考会话摘要回答", "params": {}}
        if memories:
            return {"action": ACTION_REPLY, "reason": "参考召回记忆回答", "params": {}}
        if any(k in raw for k in ("来着", "干啥", "什么来着")):
            return {"action": ACTION_REPLY, "reason": "无可用摘要", "params": {}}
        return {
            "action": ACTION_REPLY,
            "reason": "普通闲聊",
            "params": {},
        }

    def reply(self, state: dict, plan: dict) -> str:
        raw = state.get("raw_input", "") or ""
        memories = state.get("memories") or []
        recent = state.get("recent_dialogue") or []
        summary = state.get("conversation_summary") or ""
        if recent and any(k in raw for k in ("刚才说", "刚说了", "说了什么", "上一句", "我之前说")):
            last = recent[-1]
            user_part = last.split("老人：", 1)[-1].split("／", 1)[0]
            return f"您刚才说的是：{user_part}"
        if summary and any(k in raw for k in ("来着", "干啥", "什么来着", "几号", "几点", "安排", "去哪")):
            first = summary.split("｜", 1)[0].strip()
            answer = first[1:] if first.startswith("我") else first
            return f"您之前提过：{answer}"
        if memories:
            return f"记得您之前提过：{memories[0]}"
        if any(k in raw for k in ("来着", "干啥", "什么来着")):
            return "这个我一时记不清了。"
        return "我听着呢，您接着说。"

    def reply_stream(self, state: dict, plan: dict) -> Iterator[str]:
        text = self.reply(state, plan)
        for i in range(0, len(text), 3):
            yield text[i : i + 3]
            time.sleep(0.05)

    def summarize(self, dialogue: list[str], previous_summary: str = "") -> dict:
        new_text = " ".join(dialogue)
        merged = f"{previous_summary}；{new_text}" if previous_summary else new_text
        return {"summary": merged[:100], "open_items": []}


class UnsupportedResponseFormat(Exception):
    """接口不支持 response_format 时抛出。"""


def _chat_url(base_url: str) -> str:
    """拼接 /chat/completions，base_url 已含 /v1 时不重复拼接。"""
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _extract_json(content: str) -> dict:
    """优先整体解析，失败则从回复里提取第一个 JSON 对象。"""
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise PlanParseError("无法从模型回复中提取 JSON 对象")


class OpenAIClient(LLMClient):
    """走 OpenAI 兼容协议的客户端，base_url/model/api_key 全部来自配置。"""

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = base_url or config.LLM_BASE_URL
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        self.timeout = timeout or config.LLM_TIMEOUT

    def plan(self, state: dict) -> dict:
        messages = [
            {"role": "system", "content": build_system_prompt(state)},
            {"role": "user", "content": state.get("raw_input", "")},
        ]
        return parse_plan(_extract_json(self._complete(messages))).model_dump()

    def reply(self, state: dict, plan: dict) -> str:
        messages = [
            {"role": "system", "content": build_reply_prompt(state)},
            {"role": "user", "content": state.get("raw_input", "")},
        ]
        try:
            return (self._chat(messages, response_format=None) or "").strip()
        except Exception as exc:
            logger.warning("回复生成失败：%s", exc)
            return ""

    def reply_stream(self, state: dict, plan: dict) -> Iterator[str]:
        messages = [
            {"role": "system", "content": build_reply_prompt(state)},
            {"role": "user", "content": state.get("raw_input", "")},
        ]
        payload = {"model": self.model, "messages": messages, "temperature": 0.7, "stream": True}
        url = _chat_url(self.base_url)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[len("data: ") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0]["delta"].get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta

    def summarize(self, dialogue: list[str], previous_summary: str = "") -> dict:
        system = "你是摘要助手。把下面的对话压缩成不超过100字的中文摘要，并列出未完成事项。只输出 JSON：{\"summary\":\"摘要\",\"open_items\":[\"未完成事项\"]}。没有未完成事项时 open_items 为空数组。"
        user = "\n".join(dialogue)
        if previous_summary:
            user = f"已有摘要：{previous_summary}\n请在已有摘要基础上合并下面新增的对话，不要重写：\n{user}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        data = _extract_json(self._complete(messages))
        summary = str(data.get("summary", "")).strip()[:100]
        open_items = data.get("open_items") or []
        if not isinstance(open_items, list):
            open_items = []
        return {"summary": summary, "open_items": [str(x) for x in open_items]}

    def _complete(self, messages: list) -> str:
        try:
            return self._chat(messages, response_format={"type": "json_object"})
        except UnsupportedResponseFormat:
            logger.warning("接口不支持 response_format，回退为提示词约束并提取 JSON")
            return self._chat(messages, response_format=None)

    def _chat(self, messages: list, response_format: dict | None) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": 0.7}
        if response_format is not None:
            payload["response_format"] = response_format
        url = _chat_url(self.base_url)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_exc = None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if response_format is not None and resp.status_code == 400:
                    raise UnsupportedResponseFormat()
                resp.raise_for_status()
                body = resp.json()
                return body["choices"][0]["message"]["content"]
            except UnsupportedResponseFormat:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                raise
        raise last_exc


def get_client() -> LLMClient:
    if config.LLM_API_KEY and config.LLM_API_KEY != "sk-placeholder":
        return OpenAIClient()
    return FakeClient()
