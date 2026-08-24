# 流量包推荐 LangGraph Agent

GitHub: https://github.com/Peng2505/AI-agent


基于开源教程 [LangGraphChatBot](https://github.com/NanGePlus) 第四期 **二次开发**：业务改为流量套餐推荐，模型改为通义千问（环境变量），并补上健康检查、业务对话接口与关键字评测。

知识检索走 **Chroma**（不是 pgvector）；PostgreSQL 只做会话检查点与长期记忆。

## 架构（三句话）

用户问题进入 `agent`，需要时调用工具。工具名含 `retrieve` 的会先 `grade_documents`，不相关则 `rewrite`（最多 3 次）；业务工具直接进入 `generate`。会话状态中持久化学生身份、月用量、目标套餐与待确认状态；办理采用“二次确认 → 本地待办工单 → 模拟业支受理”。开通结果以模拟业支 JSON 为准（第一次查询多为 provisioning，第二次查询变为 success），**不是**生产运营商 BOSS。

## 声明

本仓库是个人二次开发结果，**不是**运营商生产系统，**没有**对接真实业支。适合作为 Agent / AI 应用实习作品集。请勿将 `.env` 中的真实 Key 提交到 Git。

克隆后在本目录执行命令（把 `python` 换成你的解释器，例如 `D:\Anaconda\envs\langgraph\python.exe`）：

```bat
cd /d D:\data-plan-langgraph-agent
python main.py
```

依赖若缺失：

```bat
python -m pip install -r requirements.txt
```

其它包（langgraph / fastapi / langchain-openai / chromadb / psycopg 等）以你现有 `langgraph` 环境为准。

## 配置

```bat
copy .env.example .env
```

编辑 `.env`，填入 `DASHSCOPE_API_KEY`。不要把真实 Key 提交到 Git。

## 启动步骤

1. Postgres（仅数据库，应用仍本机跑）：

```bat
docker compose up -d
```

若本机 5432 已被占用，改 `docker-compose.yml` 端口，并同步改 `.env` 的 `DB_URI`。

2. 灌知识库：

```bat
python vectorSaveTest.py
```

3. 命令行试跑（可选）：

```bat
python demoRagAgent.py
```

4. API：

```bat
python main.py
```

- `GET /health`
- `POST /v1/chat`  body: `{"user_id","conversation_id","message","stream"}`
- `POST /v1/chat/completions`  给 Gradio 用的 OpenAI 兼容协议
- `POST /v1/bss/provision`  模拟业支受理（与 Agent 共用内存函数，避免同进程 HTTP 死锁）
- `GET /v1/bss/tickets/{ticket_id}`  查回执；每查一次会推进异步状态

5. Web（另开终端，同一 conda 环境）：

```bat
python webUI.py
```

若设置了 `APP_API_KEY`，Gradio 会自动带 `Authorization: Bearer ...`。

6. 评测（API 已启动）：

```bat
python eval/run_eval.py
python eval/run_conversation_eval.py
```

当前结果：单轮用例以 `eval/run_eval.py` 为准；多轮含画像/确认/幂等/业支查单。结果分别写入 `eval/last_result.json` 与 `eval/last_conversation_result.json`。

可选 LangSmith：在 `.env` 填写 `LANGCHAIN_API_KEY` 后重启 `main.py`，到 smith.langchain.com 查看 Trace。

工单查询：`GET /v1/orders?user_id=xxx`，文件落在 `output/orders.json`。模拟业支票据在 `output/bss_tickets.json`。简历请写「模拟业支」，不要写已对接运营商。

## 工具

| 名称 | 作用 |
|------|------|
| retrieve_plans | RAG 检索 FAQ/规则 |
| lookup_plan | 权威价表 JSON |
| estimate_overage | 超套试算与升档建议 |
| recommend_plan | 按用户资格和月用量选择月费最低的合规套餐 |
| create_order | 二次确认后生成待办工单并提交模拟业支受理，当次不是开通成功 |
| query_ticket | 查询模拟业支回执；第二次查询才可能变为 success |

回复末尾会带 `本次调用工具` 与 `rewrite_count`。
