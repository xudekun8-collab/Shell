# 项目约定

本科毕业设计：老年人陪伴与认知活动训练系统。仓库包含两个独立部分：
- `backend/`：Python 3.11 + FastAPI + LangGraph + MySQL 8.0
- `miniprogram/`：微信小程序原生（WXML / WXSS / JavaScript）

## 一、架构不变量（违反即视为错误，不接受"更优雅"的替代方案）

1. 智能体流程固定为四节点：感知 perceive → 记忆检索 retrieve → 决策规划 plan → 执行交互 act，用 langgraph 的 `StateGraph` + 条件边组织。
2. **动作白名单只有 6 个**：`reply`（普通回复）、`start_game`（启动认知小游戏）、`start_assessment`（简易测评）、`suggest_rest`（建议休息）、`remind`（给出提醒）、`end`（结束对话）。模型只能在规则过滤后的候选动作中选择，返回白名单外的值一律降级为 `reply`。
3. **规则闸门在模型之前执行**，用纯 Python 实现，不交给模型判断。规则详见 `backend/app/agent/rules.py`。
4. 记忆分三层：画像（profile 表）、事件记忆（memories.layer='event'）、会话摘要（conversations.summary）。任何记忆必须可查看、可删除，删除后不得再被召回。
5. **不做疾病诊断，不给医疗结论**。命中药物、剂量、病情、诊断、治疗、检查结果类提问时，返回固定转介话术模板（模板写在 `backend/app/agent/rules.py` 常量里，不由模型生成）。
6. 不实现语音识别、语音合成、定时推送、微信登录、支付、家属独立账号。小程序里可以有语音按钮，但必须置灰并提示"暂未开放"。

## 二、依赖与版本

- 后端直接依赖仅允许：`fastapi`、`uvicorn`、`sqlalchemy`、`pymysql`、`pydantic`、`python-dotenv`、`httpx`、`langgraph`、`pytest`。
- **数据库使用 MySQL 8.0**（学校要求），连接串通过 `DATABASE_URL` 配置，形如 `mysql+pymysql://root:密码@127.0.0.1:3306/elder_care?charset=utf8mb4`，字符集必须是 `utf8mb4`。
- **同时保留 SQLite 作为离线回退**：pytest 一律用内存 SQLite，不连真实 MySQL；`DATABASE_URL` 换回 `sqlite:///...` 时必须仍能跑通。这是为了让答辩现场断网或数据库服务起不来时还有演示方案，不是二选一。
- **`langgraph` 会带进 `langchain-core`、`langsmith`、`langgraph-checkpoint` 等传递依赖，这是它自身的硬依赖，允许存在于环境中；但业务代码中禁止 `import langchain_core`、`langsmith`、`langgraph.prebuilt`，也禁止使用 `create_react_agent` 等预置智能体，只允许使用 `StateGraph`、`START`、`END`、条件边这几样最小能力。**
- 首次安装完成后立即 `pip freeze > backend/requirements.txt` 锁定版本，此后不得升级任何依赖。当前锁定版本为 `langgraph==1.2.20`、`sqlalchemy==2.1.8`、`fastapi==0.162.1`、`PyMySQL==1.2.3`，写代码前先确认 API 属于这一版，不要照搬旧教程。
- **不使用 checkpointer**（不引入 SqliteSaver / MemorySaver）。每次请求由 `thread_id` 从数据库组装 State，图本身无状态，`compile()` 时不传 checkpointer，服务重启不丢上下文。
- 大模型统一走 OpenAI 兼容协议（`POST {base_url}/chat/completions`），`base_url`、`model`、`api_key` 全部从 `.env` 读取，默认 DeepSeek。代码里不得出现任何厂商硬编码。

## 三、目录结构（新文件必须落在对应位置，不要另起炉灶）

```
backend/
  app/
    main.py                 # FastAPI 入口，挂载路由，/api/health
    config.py               # 读 .env，提供 database_url()
    api/
      chat.py               # POST /api/chat
      games.py              # 游戏开始/提交
      records.py            # 训练记录查询
      memory.py             # 记忆查询/删除
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
  utils/request.js  config.js
  pages/chat/  pages/game/  pages/records/  pages/memory/
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
| 用户 ID 怎么来 | 开发期用前端固定传 `demo_user_1`，不做登录 |
| 语音 | 一律不实现，按钮置灰 |
| 提醒 | 只在动作层面支持 `remind`，不实现实际定时推送 |
| 家属端 | 小程序内一个只读记录页，不做账号 |
| 测评 | `start_assessment` 只返回一句话说明 + 3 道固定题，不建完整测评模块 |
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
- 不允许新增依赖；确实需要必须先说明理由并等待确认。
- 验收里要求"实际执行并贴出输出"的，必须真跑。环境确实不具备时要如实说明，不得用"编译通过""等价校验"替代运行时结果。
