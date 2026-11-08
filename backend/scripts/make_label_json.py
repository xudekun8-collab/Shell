"""把人工填好的 data/memory_labels.txt 转成 data/memory_labels.json。"""
import json
import re
from pathlib import Path

TXT_PATH = Path("data/memory_labels.txt")
JSON_PATH = Path("data/memory_labels.json")

GROUP_HEAD = re.compile(r"^\[(\d+)\]\s*查询：(.*)$")
CAND = re.compile(r"^　?\s*([abcd])\.\s*id=(\d+)\s*(.*)$")
PICK = re.compile(r"^\s*我选：(.+)$")
ID_ONLY = re.compile(r"id=(\d+)|^(\d+)$")


def parse() -> list[dict]:
    rows: list[dict] = []
    current: dict | None = None
    cand_map: dict[str, int] = {}
    for line in TXT_PATH.read_text(encoding="utf-8").splitlines():
        head = GROUP_HEAD.match(line.strip())
        if head:
            if current is not None:
                rows.append(current)
            current = {"query": head.group(2).strip(), "label": None}
            cand_map = {}
            continue
        if current is None:
            continue
        cand = CAND.match(line)
        if cand:
            cand_map[cand.group(1)] = int(cand.group(2))
            continue
        pick = PICK.match(line)
        if pick:
            raw = pick.group(1).strip().strip("_").strip()
            if not raw or raw in {"____", "-"}:
                continue
            low = raw.lower()
            if low == "none":
                continue
            if low in cand_map:
                current["label"] = cand_map[low]
                continue
            m = ID_ONLY.search(raw)
            if m:
                current["label"] = int(m.group(1) or m.group(2))
    if current is not None:
        rows.append(current)
    return rows


def main() -> None:
    if not TXT_PATH.exists():
        print(f"未找到 {TXT_PATH}，请先运行 scripts/make_label_txt.py")
        return
    rows = parse()
    labeled = [r for r in rows if r["label"] is not None]
    missing = [i + 1 for i, r in enumerate(rows) if r["label"] is None]
    JSON_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"共 {len(rows)} 组，已填 {len(labeled)} 组，未填 {len(missing)} 组")
    if missing:
        print("未填的组：" + "、".join(str(i) for i in missing))
    print(f"已写入 {JSON_PATH}")


if __name__ == "__main__":
    main()
