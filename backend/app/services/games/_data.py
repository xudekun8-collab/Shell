"""游戏题库读取。"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "game_items"


def load(game_type: str) -> dict:
    path = DATA_DIR / f"{game_type}.json"
    return json.loads(path.read_text(encoding="utf-8"))
