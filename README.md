# 流量包推荐 LangGraph Agent

GitHub: https://github.com/Peng2505/AI-agent
## 这个项目做什么

这是一个**流量套餐推荐 Agent**（个人实践 / 开源项目二次开发）。

用户可以用自然语言咨询套餐、按是否学生和月用量做推荐、试算超套费用，并走「二次确认 → 待办工单 → 模拟业支受理/查进度」。  
数字以价表和工具 JSON 为准，避免模型口算；办理**不会真正开通或扣费**，开通结果以模拟业支回执为准。
技术上用 LangGraph 做工具路由和 RAG（Chroma），PostgreSQL 做会话记忆，FastAPI + Gradio 提供对话界面。


基于开源项目 [LangGraphChatBot](https://github.com/NanGePlus) 第四期 **二次开发**：业务改为流量套餐推荐，模型改为通义千问（环境变量），并补上健康检查、业务对话接口与关键字评测。知识检索走 **Chroma**（不是 pgvector）；PostgreSQL 只做会话检查点与长期记忆。

##技术栈
Python · LangGraph · LangChain · 通义千问 · Chroma · PostgreSQL · FastAPI · Gradio · Docker · LangSmith

| 分层 | 技术 |
|------|------|
| 语言 | Python 3 |
| Agent 编排 | LangGraph（StateGraph：agent / 工具 / 文档评分 / Query Rewrite / 生成） |
| LLM 与 Embedding | 阿里云通义千问（DashScope OpenAI 兼容接口），Key 走环境变量 |
| RAG | Chroma（本地向量库，知识为套餐 Markdown） |
| 业务工具 | 权威价表、套餐推荐、超套试算、待办工单、模拟业支查单（LangChain Tool） |
| 记忆 | PostgreSQL：`PostgresSaver` 会话检查点 + `PostgresStore` 跨会话记忆；消息裁剪 |
| 接口 | FastAPI（`/v1/chat`、OpenAI 兼容协议、`/health`、`/v1/orders`、`/v1/bss`） |
| 前端 | Gradio（登录、多会话聊天） |
| 可观测 | 可选 LangSmith；回复带工具名与 rewrite_count |
| 评测 | 单轮 / 多轮关键字回归（`eval/`） |
| 运行环境 | Docker Compose 启动 PostgreSQL（镜像 `pgvector/pgvector:pg15`，用于 Store 扩展；**RAG 不用 pgvector**） |

依赖见 `requirements.txt`。配置模板见 `.env.example`。

## 架构

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
