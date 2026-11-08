"""验证最新备份可恢复：导入临时库 elder_care_verify，查 demo_user_1，再删临时库。"""
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

BACKUP_ROOT = Path(r"D:\毕业设计_backup\db")
MYSQL = Path(r"D:\mysql\bin\mysql.exe")
ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"
VERIFY_DB = "elder_care_verify"


def load_database_url() -> str:
    if not ENV_PATH.exists():
        print(f"找不到 {ENV_PATH}", file=sys.stderr)
        sys.exit(1)
    text = ENV_PATH.read_text(encoding="utf-8")
    m = re.search(r"^DATABASE_URL=(.+)$", text, re.MULTILINE)
    if not m:
        print("backend/.env 里没有 DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return m.group(1).strip()


def main() -> None:
    parsed = make_url(load_database_url())
    user = parsed.username or ""
    password = parsed.password or ""
    host = parsed.host or "127.0.0.1"
    port = parsed.port or 3306

    if not MYSQL.exists():
        print(f"找不到 mysql：{MYSQL}", file=sys.stderr)
        sys.exit(1)

    backups = sorted(
        BACKUP_ROOT.glob("elder_care_*.sql"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        print("没有可验证的备份文件", file=sys.stderr)
        sys.exit(1)
    latest = backups[0]

    env = dict(os.environ)
    env["MYSQL_PWD"] = password
    base = [str(MYSQL), f"--host={host}", f"--port={port}", f"--user={user}"]

    def run(sql: str, use_db: bool = False):
        args = base + ([VERIFY_DB] if use_db else [])
        return subprocess.run(args, env=env, input=sql, capture_output=True, text=True)

    r = run(f"DROP DATABASE IF EXISTS {VERIFY_DB}; CREATE DATABASE {VERIFY_DB} DEFAULT CHARACTER SET utf8mb4;")
    if r.returncode != 0:
        print("建临时库失败：", r.stderr, file=sys.stderr)
        sys.exit(1)

    sql_content = latest.read_text(encoding="utf-8").replace("`elder_care`", "`elder_care_verify`")
    r = run(sql_content)
    if r.returncode != 0:
        print("导入备份失败：", r.stderr, file=sys.stderr)
        run(f"DROP DATABASE IF EXISTS {VERIFY_DB};")
        sys.exit(1)

    q = run("SELECT COUNT(*) FROM users WHERE id='demo_user_1';", use_db=True)
    if q.returncode != 0:
        print("查询失败：", q.stderr, file=sys.stderr)
        run(f"DROP DATABASE IF EXISTS {VERIFY_DB};")
        sys.exit(1)
    lines = [ln for ln in q.stdout.splitlines() if ln.strip()]
    count = lines[-1].strip() if lines else "0"
    print(f"最新备份：{latest}")
    print(f"demo_user_1 行数：{count}")
    if not count.isdigit() or int(count) < 1:
        print("验证失败：demo_user_1 行数小于 1", file=sys.stderr)
        run(f"DROP DATABASE IF EXISTS {VERIFY_DB};")
        sys.exit(1)

    run(f"DROP DATABASE IF EXISTS {VERIFY_DB};")
    print("临时库 elder_care_verify 已删除")


if __name__ == "__main__":
    main()
