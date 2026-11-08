# 备份与恢复

## 备份命令

在仓库根目录执行：

```bash
python scripts/backup_db.py
```

- 从 `backend/.env` 读 `DATABASE_URL`，用 `sqlalchemy.make_url` 解析 user/password/host/port/dbname。
- 调 `D:\mysql\bin\mysqldump.exe`，参数 `--single-transaction --default-character-set=utf8mb4 --databases <db>`。
- 密码通过环境变量 `MYSQL_PWD` 传入，不出现在命令行参数里。
- 输出到 `D:\毕业设计_backup\db\elder_care_YYYYMMDD_HHMMSS.sql`。
- 保留最近 7 份，更早的自动删除。

## 保留策略

每次备份后只保留最新的 7 个 `elder_care_*.sql`，超出的删除。答辩前建议手动再存一份到 U 盘或网盘。

## 恢复步骤

1. 找到要恢复的备份文件 `D:\毕业设计_backup\db\elder_care_*.sql`。
2. 恢复时务必先确认目标库是干净的（或另建新库），不要把备份直接灌回正在用的 `elder_care`，否则会覆盖演示数据。
3. 手动恢复命令：

```bash
set MYSQL_PWD=<密码>
D:\mysql\bin\mysql.exe -u root -h 127.0.0.1 -P 3306 < D:\毕业设计_backup\db\elder_care_xxxx.sql
```

> 上面这条 `--databases` 备份里自带 `CREATE DATABASE elder_care`，直接执行会重建/覆盖 `elder_care` 库，所以只在确定要整体回滚时用。

## 验证（不覆盖演示库）

```bash
python scripts/verify_restore.py
```

该脚本做的是：把最新备份导入一个临时库 `elder_care_verify`，查询 `SELECT COUNT(*) FROM users WHERE id='demo_user_1'`，结果必须 >= 1，然后 `DROP DATABASE elder_care_verify`。全程不碰演示库 `elder_care`。

## 常见故障

- 密码错：`mysqldump` 报 Access denied。检查 `backend/.env` 里的密码与 MySQL 实际密码是否一致。
- 找不到 mysqldump/mysql：脚本用的绝对路径 `D:\mysql\bin\...`，路径不对就报错退出。
- 备份文件为空：确认 MySQL 在 127.0.0.1:3306 监听。
