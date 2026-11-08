# 项目约定

本科毕业设计：老年人陪伴与认知活动训练系统。仓库包含两个独立部分：
- `backend/`：Python 3.11 + FastAPI + LangGraph + MySQL 8.0
- `miniprogram/`：微信小程序原生（WXML / WXSS / JavaScript）

> **修订记录**
> - 2026-11-08：按"完整系统交付"目标修订。解除"不实现语音 / 不实现微信登录 / 不做家属账号"三项限制；
>   用户身份改为服务端签发 token（客户端不得自报 `user_id`）；放开鉴权、本地向量召回、数据库迁移所需的依赖。
>   其余架构不变量（四节点、6 动作白名单、规则先于模型、三层记忆、不做医疗诊断、不用 checkpointer）一律不变。

## 一、架构不变量（违反即视为错误，不接受"更优雅"的替代方案）

1. 智能体流程固定为四节点：感知 perceive → 记忆检索 retrieve → 决策规划 plan → 执行交互 act，用 langgraph 的 `StateGraph` + 条件边组织。
2. **动作白名单只有 6 个**：`reply`（普通回复）、`start_game`（启动认知小游戏）、`start_assessment`（简易测评）、`suggest_rest`（建议休息）、`remind`（给出提醒）、`end`（结束对话）。模型只能在规则过滤后的候选动作中选择，返回白名单外的值一律降级为 `reply`。
3. **规则闸门在模型之前执行**，用纯 Python 实现，不交给模型判断。规则详见 `backend/app/agent/rules.py`。
4. 记忆分三层：画像（profile 表）、事件记忆（memories.layer='event'）、会话摘要（conversations.summary）。任何记忆必须可查看、可删除，删除后不得再被召回。
5. **不做疾病诊断，不给医疗结论**。命中药物、剂量、病情、诊断、治疗、检查结果类提问时，返回固定转介话术模板（模板写在 `backend/app/agent/rules.py` 常量里，不由模型生成）。
6. 语音、微信登录、家属账号已纳入范围（2026-11-08 修订，实现顺序见 `Codex提示词-24天倒排.md` 的 M1/M2）：
   - 语音：ASR 用微信同声传译插件，TTS 用云服务；网络或插件不可用时回退纯文字；**音频不落库**。
   - 登录：小程序 `wx.login` 取 code，服务端 `jscode2session` 换 openid 并签发 token；演示期 `DEMO_MODE=1` 保留 `demo_user_1` 后门。
   - 家属：`role=family` 只读角色，邀请码绑定；只能看摘要、训练记录与危机告警，**不得看原始对话全文**。
   - 仍不实现：支付、订阅消息/定时推送、任何医疗诊断结论。

## 二、依赖与版本

- 运行时直接依赖以 `backend/requirements.txt` 为准，基线为：`fastapi`、`uvicorn`、`sqlalchemy`、`pymysql`、`pydantic`、`python-dotenv`、`httpx`、`langgraph`、`PyYAML`（`app/agent/rules.py` 加载 `data/safety_rules.yaml`，当前 32 条规则 / 5 套话术）、`pytest`。
- 工具链依赖允许存在于环境，但**不得在 `app/` 里 import**：`matplotlib`、`numpy`、`pillow`，只在 `scripts/make_figures.py` 出图用。
- 因 2026-11-08 修订新增的能力，允许且仅允许再加这三类：`PyJWT`（token 签发）、`fastembed` 或 `onnxruntime`（本地向量召回）、`alembic`（表结构迁移）。除此外不得新增依赖。
- 新增依赖必须先说明用途、锁定版本、写入 `backend/requirements.txt`，并保证离线可安装（答辩现场断网也要能起）。
- **数据库使用 MySQL 8.0**（学校要求），连接串通过 `DATABASE_URL` 配置，形如 `mysql+pymysql://root:密码@127.0.0.1:3306/elder_care?charset=utf8mb4`，字符集必须是 `utf8mb4`。
- **同时保留 SQLite 作为离线回退**：pytest 一律用内存 SQLite，不连真实 MySQL；`DATABASE_URL` 换回 `sqlite:///...` 时必须仍能跑通。这是为了让答辩现场断网或数据库服务起不来时还有演示方案，不是二选一。
- **`langgraph` 会带进 `langchain-core`、`langsmith`、`langgraph-checkpoint` 等传递依赖，这是它自身的硬依赖，允许存在于环境中；但业务代码中禁止 `import langchain_core`、`langsmith`、`langgraph.prebuilt`，也禁止使用 `create_react_agent` 等预置智能体，只允许使用 `StateGraph`、`START`、`END`、条件边这几样最小能力。**
- 首次安装完成后立即 `pip freeze > backend/requirements.txt` 锁定版本；新增依赖按上一条流程加入并锁定，已有依赖不得随意升级。当前基线为 `langgraph==1.2.20`、`sqlalchemy==2.1.8`、`fastapi==0.162.1`、`PyMySQL==1.2.3`，写代码前先确认 API 属于这一版，不要照搬旧教程。
- **不使用 checkpointer**（不引入 SqliteSaver / MemorySaver）。每次请求由 `thread_id` 从数据库组装 State，图本身无状态，`compile()` 时不传 checkpointer，服务重启不丢上下文。
- 大模型统一走 OpenAI 兼容协议（`POST {base_url}/chat/completions`），`base_url`、`model`、`api_key` 全部从 `.env` 读取，默认 DeepSeek。代码里不得出现任何厂商硬编码。

## 三、目录结构（新文件必须落在对应位置，不要另起炉灶）

```
backend/
  app/
    main.py                 # FastAPI 入口，挂载路由，/api/health
    config.py               # 读 .env，提供 database_url()
    api/
      auth.py               # 登录签发 token（wx / demo）
      chat.py               # POST /api/chat 与 /api/chat/stream
      games.py              # 游戏开始/提交
      records.py            # 训练记录查询
      memory.py             # 记忆查询/删除
      family.py             # 家属端只读视图（overview / records / alerts）
      deps.py               # current_user / require_role
    agent/
      state.py              # State TypedDict
      graph.py              # StateGraph 组装
      rules.py              # 规则闸门 + 固定话术模板
      actions.py            # 6 个动作的白名单定义
      nodes/
        perceive.py
        retrieve.py
        plan.py
        act.py
    llm/
      client.py             # OpenAI 兼容客户端 + FakeClient
      prompts.py            # 系统提示词
      schemas.py            # Plan 的 Pydantic 模型
    memory/
      store.py              # 记忆读写
      compress.py           # 会话摘要压缩
      scoring.py            # 召回打分（字符二元组）
      embedding.py          # 本地向量索引，字符+向量混合召回
    db/
      models.py             # 6 张表
      session.py            # engine / SessionLocal / to_time
      init_db.py
    services/
      game_engine.py        # 游戏引擎
      difficulty.py         # 难度三级 + 自适应
      records.py            # 训练记录汇总
  scripts/
    seed_demo.py
    switch_to_mysql.py      # 从 SQLite 迁数据（如需要）
  tests/
  data/game_items/          # 题库 JSON
  requirements.txt
  .env.example
miniprogram/
  app.js  app.json  app.wxss
  utils/request.js  config.js  user.js  constants.js
  pages/chat/  pages/game/  pages/records/  pages/memory/  pages/family/
```

## 四、代码规范

- 标识符、表名、接口字段一律英文；注释、日志、UI 文案一律中文。
- 代码和文案里**禁止使用 emoji**（这是答辩产物）。
- 所有接口请求体和响应体用 Pydantic 模型定义在 `app/api/` 对应文件里，不要裸 dict 进出。
- 关键分支必须打日志（`logging`，中文消息），记录 `user_id`、动作、耗时。
- 数据库访问统一走 SQLAlchemy 2.0 风格（`select()`），不写裸 SQL 字符串拼接。

## 五、数据库方言兼容要求（关键，别踩）

1. **自增主键统一用 `models.py` 里的 `BigIntPK`**（`BigInteger` 在 MySQL 下是 `BIGINT AUTO_INCREMENT`，在 SQLite 下退化为 `INTEGER`）。不要直接写 `BigInteger`：SQLite 里只有 `INTEGER PRIMARY KEY` 才是 rowid 别名，`BIGINT` 建主键不会自增，插入会得到 NULL 主键且不报错，属于静默错误。
2. **TIME 字段**（`wake_time`、`sleep_time`）在 MySQL 下是 `datetime.time`，在 SQLite 下取出来是字符串 `"07:00:00"`。所有模块一律通过 `app.db.session.to_time(value)` 取值，不得直接比较字符串。
3. **JSON 字段**统一用 SQLAlchemy 的 `JSON` 类型，不要用 MySQL 专有的 `JSON` 方言类，也不要在代码里手工 `json.dumps`。
4. MySQL 建表必须带 `utf8mb4`，中文内容和表情以外的标点都不能乱码。
5. 时间一律用 `datetime.now()`（本地时间），不要用 `utcnow()`，因为夜间免打扰规则按本地作息判断。

## 六、默认决策表（遇到歧义按这里定，不要反问用户）

| 歧义点 | 默认决策 |
|---|---|
| 数据库 | MySQL 8.0，`127.0.0.1:3306/elder_care`；pytest 用内存 SQLite；两者都必须能用 |
| 连接串来源 | 只从 `.env` 的 `DATABASE_URL` 读，不在代码里拼账号密码 |
| 用户 ID 怎么来 | 服务端签发 token 绑定 openid；客户端不得自报 `user_id`；演示期 `DEMO_MODE=1` 可走 `demo_user_1` 后门 |
| 语音 | ASR 用微信同声传译插件，TTS 用云服务；网络或插件不可用时回退纯文字；音频不落库 |
| 提醒 | 只在动作层面支持 `remind`，不实现真实订阅消息推送（如需推送单独立项） |
| 家属端 | `role=family` 只读账号，邀请码绑定；只看摘要、记录、告警，不看原始对话全文 |
| 测评 | `start_assessment` 返回一句话说明 + 3 道固定题；不建独立测评模块（题目待补） |
| 会话状态 | 不落 checkpoint，每次从 DB 组装 |
| 模型不可用 | 自动降级到 FakeClient，接口不报 500 |
| 中文分词/关键词规则 | 用 `in` 判断关键词列表，不引入分词库 |
| 图片素材 | 用纯文字/色块卡片，不引入图片资源 |
| 小程序单位 | 一律 `rpx`，字号最小 32rpx |

## 七、数据安全（MySQL 专用）

- **绝对禁止**执行 `DROP DATABASE`、`TRUNCATE`、`DELETE FROM`（无 WHERE）、`--initialize` 覆盖已有数据目录、删除 `data` 目录这类破坏性操作。需要清空数据时只能通过 `scripts/seed_demo.py` 逐表清理，且必须先打印将被清理的行数。
- 发现机器上已有 MySQL 实例或数据目录时，**不要重新初始化、不要改配置、不要动已有库**，先报告现状再由用户决定。
- 建库建表只允许 `CREATE DATABASE IF NOT EXISTS`、`CREATE TABLE IF NOT EXISTS`。

## 八、每次交付的要求

- 一次只做一个阶段，不顺手改其他模块；**只做用户本次指令中明确要求的那一个阶段，不要提前实现后面的阶段**。
- 改完必须给出：改动文件列表、跑验收的命令、实际输出。
- 不允许为了让测试通过而修改测试预期值。
- 新增依赖、改接口字段、改表结构，必须先说明理由、影响范围和回滚方式，等我确认后再动。
- 验收里要求"实际执行并贴出输出"的，必须真跑。环境确实不具备时要如实说明，不得用"编译通过""等价校验"替代运行时结果。
