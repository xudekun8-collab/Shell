"""前端静态红线检查：字号下限、禁 break-all、业务页禁止 demo_user_1 硬编码。

用 Python 实现而不是在批处理里拼 PowerShell 单行命令：
  - 正则与路径都在文件里，不受 cmd 引号转义影响；
  - 失败时能直接打印文件名和行号，方便定位。
退出码：0 通过，1 有违规。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "miniprogram"

# 老人端字号下限 40rpx（AGENTS.md 六：小程序单位一律 rpx，字号最小 32rpx；
# check.bat 采用更严的 40rpx 作为交付红线）
FONT_RE = re.compile(r"font-size:\s*(\d+)rpx")
MIN_FONT_RPX = 40

VIOLATIONS = []


def report(kind, path, lineno, text):
    rel = path.relative_to(ROOT.parent).as_posix()
    VIOLATIONS.append(f"{kind} {rel}:{lineno}  {text.strip()}")


def check_fonts():
    for path in list(ROOT.rglob("*.wxss")) + list(ROOT.rglob("*.wxml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in FONT_RE.finditer(line):
                size = int(match.group(1))
                if size < MIN_FONT_RPX:
                    report("裸写字号过小", path, lineno, line)


def check_break_all():
    for path in ROOT.rglob("*.wxss"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "break-all" in line:
                report("使用了 break-all", path, lineno, line)


def check_demo_hardcode():
    for path in ROOT.rglob("*.js"):
        # 登录页是演示后门的唯一合法位置
        if "pages\\login\\" in str(path) or "pages/login/" in path.as_posix():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "demo_user_1" in line:
                report("业务页硬编码演示账号", path, lineno, line)


def check_sitemap():
    """隐私页面必须 disallow，且 disallow 要排在 allow 之前。"""
    path = ROOT / "sitemap.json"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    allow_at = text.find('"allow"')
    for page in ("pages/memory/memory", "pages/family/family"):
        idx = text.find(f'"disallow", "page": "{page}"')
        if idx < 0:
            VIOLATIONS.append(f"索引规则未禁用隐私页 {page}")
        elif allow_at >= 0 and idx > allow_at:
            VIOLATIONS.append(f"索引规则顺序错误：disallow 必须排在 allow 之前（{page}）")


def main():
    check_fonts()
    check_break_all()
    check_demo_hardcode()
    check_sitemap()
    if VIOLATIONS:
        print("FAIL: 静态红线检查未通过")
        for item in VIOLATIONS[:30]:
            print("  " + item)
        if len(VIOLATIONS) > 30:
            print(f"  ... 另有 {len(VIOLATIONS) - 30} 处")
        return 1
    print(f"静态红线检查通过（字号下限 {MIN_FONT_RPX}rpx、无 break-all、无演示账号硬编码、隐私页已禁索引）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
