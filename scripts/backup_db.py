"""备份 MySQL 演示库，保留最近 7 份。"""
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

BACKUP_ROOT = Path(r"D:\毕业设计_backup\db")
MYSQLDUMP = Path(r"D:\mysql\bin\mysqldump.exe")
ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"


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
    dbname = parsed.database
    user = parsed.username or ""
    password = parsed.password or ""
    host = parsed.host or "127.0.0.1"
    port = parsed.port or 3306

    if not MYSQLDUMP.exists():
        print(f"找不到 mysqldump：{MYSQLDUMP}", file=sys.stderr)
        sys.exit(1)

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = BACKUP_ROOT / f"{dbname}_{stamp}.sql"

    env = dict(os.environ)
    env["MYSQL_PWD"] = password
    cmd = [
        str(MYSQLDUMP),
        f"--host={host}",
        f"--port={port}",
        f"--user={user}",
        "--single-transaction",
        "--default-character-set=utf8mb4",
        "--databases",
        dbname,
        f"--result-file={out_path}",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print("mysqldump 失败：", result.stderr, file=sys.stderr)
        sys.exit(1)

    backups = sorted(
        BACKUP_ROOT.glob(f"{dbname}_*.sql"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[7:]:
        old.unlink()

    size = out_path.stat().st_size
    print(f"备份完成：{out_path}")
    print(f"大小：{size} 字节")


if __name__ == "__main__":
    main()
