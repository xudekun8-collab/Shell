# 演示版基线 v1

## 元信息

- 提交哈希：b5a83e2dc7b18e08af7883bce9f52b75befcd62e
- 标签名：demo-v1
- 生成时间：2026-11-08 17:23:49

## 测试

- pytest：106 passed in 1.28s

## 召回基线（数据来自 backend/data/eval_result.json，36 条人工标注）

- 默认权重（全部 36 条）：Recall@3 = 0.8333，MRR = 0.8077，命中 30/36
- 困难子集（--hard，17 条）：Recall@3 = 0.8824，MRR = 0.8679，命中 15/17
- 时间配对子集（6 组只差日期的配对记忆 + 6 条带时间词 query）：Recall@3 = 0.5000，MRR = 0.4375，命中 3/6

## 难度自适应基线（模拟用户，seed 20261108）

- strong：终档 3（first5 2.4 / last5 3.0）
- normal：终档 2（first5 2.0 / last5 2.0）
- weak：终档 1（first5 1.6 / last5 1.0）

## 题库规模

- category_sort：low / mid / high = 10 / 12 / 12 组，每组 1 题，一局抽 6 / 8 / 10 组
- memory_box：low / mid / high = 6 / 6 / 6 组，每组呈现 4 / 6 / 8 个词并配等量再认题，一局 1 组

## 接口清单（鉴权之前，共 7 个）

- POST /api/chat
- POST /api/game/start
- POST /api/game/submit
- GET /api/records/{user_id}
- GET /api/memories/{user_id}
- DELETE /api/memories/{user_id}/{memory_id}
- GET /api/greeting/{user_id}

## 已知短板

- 无鉴权（接口凭 user_id 即可读写，演示版仅局域网单用户可接受）
- 无流式输出（回复为一次性返回，不逐字流式）
- 召回打分是字符二元组 Jaccard，非向量/语义检索
- 字符召回对同义改写失效：手工构造的同义改写用例里，65 条候选仅 17 条被召回，粗筛后 28/30 仍无法把正确记忆带进 top3（这是 M2 混合召回要解决的问题）
- 游戏会话存在内存（服务重启会丢）
- 部署为本机 HTTP 明文服务，未上 HTTPS
