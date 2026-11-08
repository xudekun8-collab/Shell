# 老年人陪伴与认知活动训练系统

本科毕业设计。一个面向老年人的陪伴助手：文字聊天、两套认知小游戏（记东西 / 分分类）、三层记忆（画像 / 事件 / 会话摘要）、训练记录，全部中文口语化文案、大字号、大按钮。

## 目录结构

```
backend/          Python 3.11 + FastAPI + LangGraph + MySQL 8.0
  app/            路由、智能体四节点、记忆、游戏引擎、数据库模型
  tests/          pytest（用内存 SQLite，不连 MySQL）
  data/           题库、安全规则、消融数据
  scripts/        演示数据、出图、网络检查等脚本
miniprogram/      微信小程序（原生 WXML / WXSS / JS）
  pages/          chat / game / records / memory 四页
  utils/          request.js 请求封装、config.js 后端地址、user.js、constants.js
```

## 后端怎么起

首次安装依赖（在 `backend/` 目录下）：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

先确认 MySQL 8.0 已启动，`.env` 里的 `DATABASE_URL` 指向 `mysql+pymysql://root:<密码>@127.0.0.1:3306/elder_care?charset=utf8mb4`。
密码只写在 `.env`（已被 gitignore），不要写进任何被跟踪的文件；`.env.example` 里只有 `your-password` 占位。

启动服务：双击 `backend/start_server.bat`（等价于 `.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`）。

初始化建表与演示数据：`python -m app.db.init_db`。

跑测试：在 `backend/` 目录执行 `.venv\Scripts\python.exe -m pytest -q`。

## 小程序怎么配

1. 用微信开发者工具打开 `miniprogram/` 目录。
2. 打开 `miniprogram/utils/config.js`：电脑模拟器用默认的 `127.0.0.1` 可跑通；真机预览要把 `lan_ip` 改成电脑的局域网 IPv4（cmd 里 `ipconfig`，看无线局域网适配器 WLAN 的 IPv4，不是虚拟网卡地址），并确认后端以 `0.0.0.0` 监听。
3. 开发者工具里勾选「不校验合法域名」，否则本地 http 请求会被拦。

## 跑测试

后端测试（在 `backend/` 目录）：

```bash
.venv\Scripts\python.exe -m pytest -q
```

前端静态校验（在仓库根目录）：

```bash
node --check miniprogram/pages/chat/chat.js
```

## 已知限制

- 无登录鉴权：当前 `utils/user.js` 里用户 ID 固定为 `demo_user_1`，接口凭 user_id 即可读写，只适合局域网演示。
- 数据库依赖本机 MySQL 8.0，断网或数据库没起时后端返回 `db: degraded`，可临时把 `.env` 的 `DATABASE_URL` 切到 `sqlite:///./elder_care.db` 兜底。
- 游戏会话存在内存，后端重启后未提交的局会失效。
- 语音、家属只读账号在后续阶段接入，当前只有文字交互。

## 安全提醒（演示后门）

`DEMO_MODE=1` 时，`POST /api/auth/demo` 接受任意 `user_id` 并直接签发 token，等于整站鉴权对任何人放开。这只用于答辩现场演示；正式部署必须 `DEMO_MODE=0`（此时演示登录返回 401，旧版带 user_id 的接口返回 403）。
