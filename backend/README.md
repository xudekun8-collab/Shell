# 后端

阶段一：环境与数据层骨架。以下命令都在 `backend/` 目录下执行。

## 数据库：MySQL 8.0（免安装版，在 D:\mysql）

数据库是免安装的 ZIP 版，没有注册成 Windows 服务，**不会开机自启**。

每次开工前先启动它（双击也行）：

    D:\mysql\start_mysql.bat

停止：

    D:\mysql\stop_mysql.bat

连接参数：`127.0.0.1:3306`，用户 `root`，库 `elder_care`，字符集 `utf8mb4`。密码不写进仓库，统一在 `backend/.env` 的 `DATABASE_URL` 里配置（模板见 `.env.example`）。

建表并写入演示用户（可重复执行）：

    python -m app.db.init_db

启动服务：

    uvicorn app.main:app --reload

运行测试：

    python -m pytest

健康检查：

    curl http://127.0.0.1:8000/api/health

预期返回 `{"status":"ok","db":"ok"}`。

## 答辩断网时的回退方案

把 `backend/.env` 里的 `DATABASE_URL` 切成注释里那行 SQLite：

    DATABASE_URL=sqlite:///./elder_care.db

业务代码一行不用改，重新建表即可（`python -m app.db.init_db`）。

## 数据在哪

- MySQL 数据目录：`D:\mysql\data`（备份就整个复制这个目录，先执行 stop_mysql.bat 再复制）
- SQLite 备用库：`backend/elder_care.db`
