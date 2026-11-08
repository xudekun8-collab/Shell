"""模型输出的 Plan 数据模型与解析。"""
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["reply", "start_game", "start_assessment", "suggest_rest", "remind", "end"]


class PlanParseError(Exception):
    """模型输出无法解析为合法 Plan 时抛出。"""


class PlanModel(BaseModel):
    action: Action
    reason: str = Field(default="", max_length=40)
    params: dict = Field(default_factory=dict)


def parse_plan(data: dict) -> PlanModel:
    try:
        return PlanModel.model_validate(data)
    except Exception as exc:
        raise PlanParseError(f"模型输出解析失败：{exc}") from exc
