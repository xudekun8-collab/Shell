# 老年人陪伴与认知活动训练系统

本科毕业设计。一个面向老年人的陪伴助手：文字聊天、四种认知练习（记东西 / 分分类 / 记数字 / 生活常识）、三层记忆（画像 / 事件 / 会话摘要）、训练记录、家属只读端、自定义 tabBar 和腾讯云 ASR，全部中文口语化文案、大字号、大按钮。

## 目录结构

```
backend/          Python 3.11 + FastAPI + LangGraph + MySQL 8.0
  app/            路由、智能体四节点、记忆、游戏引擎、数据库模型
  tests/          pytest（用内存 SQLite，不连 MySQL）
  data/           题库、安全规则、消融数据
  scripts/        演示数据、出图、网络检查等脚本
miniprogram/      微信小程序（原生 WXML / WXSS / JS）
  pages/          chat / game / records / memory / family / login 六页
  custom-tab-bar/ 说话 / 练习 / 记录三项自定义底栏
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
2. `miniprogram/utils/config.js` 按运行环境选后端地址：`develop` 是局域网 http（`LAN_HOST`，改成自己电脑的 IPv4），`trial` / `release` 是正式 HTTPS 域名（`API_HOST`）。不用改代码也可以：**登录页长按顶部圆形图标**，可临时覆盖接口地址（存在本地 storage，清缓存即恢复；正式版不开放）。
3. 开发者工具里勾选「不校验合法域名」，否则本地 http 请求会被拦。
4. 真实域名需在小程序后台配置 request 合法域名，且**必须在「设置-服务内容声明-用户隐私保护指引」里声明麦克风**；否则真机上点麦克风会失败。首次录音前微信会回调 `wx.onNeedPrivacyAuthorization`，`app.js` 已实现「同意 / 不同意」弹窗，不同意时仍可打字。

## 跑测试

后端测试（在 `backend/` 目录）：

```bash
.venv\Scripts\python.exe -m pytest -q
```

前端纯函数单测（在仓库根目录，Node 18+ 自带 test runner，不需装依赖）：

```bash
node --test miniprogram/tests/format.test.js miniprogram/tests/constants.test.js miniprogram/tests/taboo.test.js
```

## 已知限制

- 鉴权：老人端与家属端分别使用 HS256 自签 token，业务接口通过 `require_role` 做角色守卫；`DEMO_MODE=0` 时演示登录关闭。小程序端只在 `develop` / `trial` 尝试演示登录，`release` 一律走 `wx.login`。
- 数据库依赖本机 MySQL 8.0，断网或数据库没起时后端返回 `db: degraded`，可临时把 `.env` 的 `DATABASE_URL` 切到 `sqlite:///./elder_care.db` 兜底。
- 游戏会话存在内存，后端重启后未提交的局会失效。
- 游戏会话只存在单进程内存；多人多进程部署需要改存数据库或 Redis。
- 邀请码绑定使用原子更新，但邀请码生成查重未加唯一索引，极端并发下仍可能生成碰撞码。
- 题目轮换状态保存在内存中且没有容量上限。
- 聊天模型、ASR 与 TTS 目前没有按用户限流，正式部署应在网关或账号层补充配额。
- 老人端记录页不显示正确率，只显示完成次数、连续天数、总用时；家属端正确率是完成局正确率的均值，仅用于练习反馈，不用于能力判断。
- 语音识别与语音合成均支持腾讯云；合成是否可用由 `TTS_PROVIDER`、语音合成开通状态和腾讯云密钥共同决定，未开通时前端静默退化。
- 聊天页内存里只保留最近 200 条消息（本地落盘 50 条），更早的对话仍留在后端库里，但老人端不再回显。

## 安全提醒（演示后门）

`DEMO_MODE=1` 时，`POST /api/auth/demo` 只为 `DEMO_USERS` 允许列表中的账号签发 token，默认仅 `demo_user_1`。这只用于答辩现场演示；正式部署必须 `DEMO_MODE=0`（此时演示登录返回 401，旧版带 user_id 的接口返回 403）。

## 质量护栏

- 一键检查：双击仓库根目录的 `scripts/check.bat`，依次跑 6 步：后端 pytest（当前基线 229 例）、前端 JS 语法、前端纯函数单测（23 例）、JSON 合法性、静态红线检查、汇总。全过打印 `ALL CHECKS PASSED`，任一失败打印 `FAIL: <步骤>` 并退出码 1。
- 静态红线由 `scripts/redline_check.py` 实现（字号 <40rpx、`break-all`、业务页硬编码 demo_user_1、隐私页未禁索引）。用 Python 而不是批处理里拼 PowerShell 单行命令，避免 cmd 引号转义问题，失败时能打印文件名和行号。
- 后端接口由 pytest 覆盖（`tests/`，用内存 SQLite + FakeClient，不连 MySQL、不调真模型）。
- 前端可测的是纯函数：`utils/format.js`（回复截断、用时与日期文案、列表 key）、`utils/constants.js`（语速归一化）、`utils/taboo.js`（忌讳词匹配）。页面里只调用，不重复实现。
- 小程序端的交互行为（点击、录音、切后台、弹窗）脚本驱动不了，仍以 `docs/manual_checklist.md` 的人工勾选为准。

## 部署

本机 HTTPS（自签证书）、备份/恢复、容器化方案详见 `docs/deploy.md`。

- HTTPS：`scripts/gen_cert.bat` 生成自签证书，`scripts/start_https.bat` 起 8443；HTTP 8000（`backend/start_server.bat`）保留并存。
- 备份：`python scripts/backup_db.py`（保留最近 7 份），恢复验证 `python scripts/verify_restore.py`（导入临时库，不覆盖演示库）。
- 容器化：`deploy/Dockerfile` / `deploy/docker-compose.yml` / `deploy/nginx.conf` 已产出，但**本机（Windows，无 Docker/WSL）未运行验证此方案**，仅作为可移植部署方案交付。
