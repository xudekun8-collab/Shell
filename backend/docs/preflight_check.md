# 答辩前自查报告

本报告只描述现状与建议，不含任何密钥真实值。结论按「演示版（局域网、仅 demo_user_1）」口径评估。

## A. 鉴权

| 接口 | 是否校验调用者身份 | 现状 |
|---|---|---|
| GET /api/records/{user_id} | 否 | 仅凭路径 user_id 读取 |
| GET /api/memories/{user_id} | 否 | 仅凭路径 user_id 读取 |
| DELETE /api/memories/{user_id}/{memory_id} | 否（仅比对 memory.user_id == 路径 user_id） | 知道 user_id + memory_id 即可软删 |
| POST /api/chat | 否 | body 里 user_id 任意 |
| POST /api/game/start | 否 | body 里 user_id 任意 |
| POST /api/game/submit | 否 | 仅凭 session_id |
| GET /api/greeting/{user_id} | 否 | 仅凭路径 user_id |

- 只需知道 user_id 就能读/删别人数据的接口：records、memories（GET 与 DELETE）、greeting 的读；chat 与 game/start 还能以任意 user_id 写。DELETE memories 是最需要关注的一处（软删）。
- 结论：演示版可接受——局域网、单演示用户、无真实多用户数据，越权面有限；生产必须加身份认证（登录态或至少服务端签发的 token），并把 user_id 与服务端身份绑定，禁止客户端自报 user_id。
- 可选缓解：本任务已加 `require_demo_token`（见 deps.py），DEMO_TOKEN 留空时完全放行；填值后 records 与 memories 的读/删接口要求 `X-Demo-Token` 头一致，chat / game / greeting 不受影响。
- 风险等级：生产高，演示低。

## B. 传输与暴露面

- 后端以 0.0.0.0:8000 明文 HTTP 监听（start_server.bat），同网段设备可访问；本机曾放行 8000 入站防火墙（firewall_allow_8000.bat），网络位置为「公用」时入站默认仍可能被拦。
- 密钥存放机制：DeepSeek key 与数据库口令都在 backend/.env，由 python-dotenv 读入进程环境变量；LLM_API_KEY 仅被 llm/client.py 用来拼 Authorization 请求头，数据库口令在 DATABASE_URL 里。backend/.env 已写入 .gitignore 且未被 git 跟踪，代码文件不硬编码任何密钥。
- 结论：演示期间建议把网络位置设为「专用」或只放行必要端口，避免公用网络长期明文暴露；答辩结束后运行 firewall_remove_8000.bat 撤掉放行规则。
- 风险等级：中。

## C. 危险动作

- wx.getUserInfo / wx.getUserProfile / wx.getSetting / wx.login / wx.getPhoneNumber：均未使用。
- 位置、剪贴板：未使用 wx.getLocation / wx.getClipboardData。
- 结论：全部「未使用」。无微信登录、无手机号收集、无定位、无剪贴板读取；user_id 由前端固定 demo_user_1。无需替换。
- 风险等级：低。

## D. 合规材料（清单，正文另行撰写）

- 服务类目：建议选无需资质的类别，如「教育 > 教育信息服务」或「工具 > 效率」；避开医疗、金融等需资质类别。
- 隐私保护指引需声明的信息项：对话文本（聊天输入与回复）、称呼（nickname）、兴趣与忌讳（interests / taboos）、训练记录（游戏成绩、用时、日期）。
- 首次使用告知位置：chat 页首次进入时，以底部小字或一条「使用须知」气泡呈现，内容约三句：本服务仅用于陪伴与认知练习、对话与训练数据只保存在本机后端、不构成任何医疗判断。

## E. 数据

- 重建：scripts/seed_demo.py 的 seed_memories(session_factory, user_id='demo_user_1') 可写入演示用事件/会话记忆；但该函数是「追加」语义，没有 reset/clean 参数，重复运行会重复插入。
- 回到干净状态：目前没有一键重置；临时做法是逐条调用 DELETE /api/memories/{user_id}/{memory_id} 软删，或直接按 user_id 清理。注意 AGENTS.md 要求清空数据必须走 seed_demo.py 且先打印将被清理的行数，而当前 seed_demo.py 尚无清理函数，属于缺口。
- 建议：给 seed_demo.py 补一个「先打印待删行数、再逐表清理」的 reset 参数（本次范围外，未实现）；答辩前确认演示库已是干净状态。
- 风险等级：中。
