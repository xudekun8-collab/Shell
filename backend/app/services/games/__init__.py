"""游戏题型注册表。"""
from app.services.games import category_sort, common_sense, memory_box, number_seq


class UnknownGameError(ValueError):
    """请求了未注册的游戏类型。"""


GAME_REGISTRY = {
    "memory_box": memory_box,
    "category_sort": category_sort,
    "number_seq": number_seq,
    "common_sense": common_sense,
}


def get_game(game_type: str):
    try:
        return GAME_REGISTRY[game_type]
    except KeyError:
        raise UnknownGameError("未知题型")
