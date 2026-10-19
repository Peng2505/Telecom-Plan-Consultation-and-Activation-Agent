# 流量包推荐 LangGraph Agent

流量套餐推荐，模型改为通义千问（环境变量），并补上健康检查、业务对话接口与关键字评测。

知识检索走 **Chroma**（不是 pgvector）；PostgreSQL 只做会话检查点与长期记忆。

## 架构（三句话）

用户问题进入 `agent`，需要时调用工具。工具名含 `retrieve` 的会先 `grade_documents`，不相关则 `rewrite`（最多 3 次）；业务工具直接进入 `generate`。会话状态中持久化学生身份、月用量、目标套餐与待确认状态；办理采用“二次确认 → 本地待办工单 → 模拟业支受理”。开通结果以模拟业支 JSON 为准（第一次查询多为 provisioning，第二次查询变为 success），**不是**生产运营商 BOSS。

## 环境：请用 Anaconda 的 `langgraph`

```bat
cd /d d:\LangGraphChatBot-main\04_RagAgent
D:\Anaconda\envs\langgraph\python.exe main.py
```

本目录新依赖若缺失，仍装进该环境：

```bat
python -m pip install python-dotenv
```

其它包（langgraph / fastapi / langchain-openai / chromadb / psycopg 等）以你现有 `langgraph` 环境为准。

## 配置

```bat
copy .env.example .env
```

编辑 `.env`，填入 `DASHSCOPE_API_KEY`。不要把真实 Key 提交到 Git。

## 一键部署（Docker Compose）

`.env` 填好 `DASHSCOPE_API_KEY` 后：

```bat
docker compose up -d --build
```

会启动 **Postgres + FastAPI(api) + Gradio(web)**。首次若本地 `chromaDB` 无集合，api 容器会自动灌库。

- 健康检查：http://127.0.0.1:8012/health  
- 网页：http://127.0.0.1:7860  
- 日志：`docker compose logs -f api`  
- 强制灌库：`set RUN_INGEST=1` 后重启 api  

会话持久化靠 Postgres Checkpointer/Store；LangSmith 仅在配置 `LANGCHAIN_API_KEY` 时做链路追踪。

### 验证是否启动成功

本机按下列步骤验收通过后，即可认为一键部署可用：

```bat
docker compose ps
```

应看到 `ragagent_postgres` / `ragagent_api` / `ragagent_web` 为 running 或 healthy。

```powershell
Invoke-WebRequest http://127.0.0.1:8012/health | Select-Object -ExpandProperty Content
```

期望包含 `"status":"ok"`、`"postgres":true`，灌库完成后还有 `"chroma_collection":true`。

再打开 http://127.0.0.1:7860 ，登录后问「经济套餐多少钱？」，能正常回复即端到端通过。

日常重启：`docker compose up -d`（改镜像依赖时再加 `--build`）。

## 本机开发启动

1. 仅起数据库：

```bat
docker compose up -d postgres
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

`API_BASE_URL` 默认 `http://127.0.0.1:8012`。若设置了 `APP_API_KEY`，Gradio 会自动带 `Authorization: Bearer ...`。

6. 评测（分层）：

```bat
python eval/run_retrieval_eval.py
python eval/run_all.py --label baseline
python eval/run_all.py --label full --with-injection --with-ragas
```

- 检索层（不需 API）：Hit Rate@K、MRR → `eval/last_retrieval_result.json`
- 忠实度层（需 API）：字段命中率、数字幻觉率 → `eval/last_faithfulness_result.json`
- 端到端：单轮 `eval/run_eval.py`、多轮 `eval/run_conversation_eval.py`
- 注入防御：`eval/run_injection_eval.py` → `interception_rate`（见 `INJECTION_GUARDRAILS.md`）
- RAGAS 对齐 + LLM-as-Judge：`eval/run_ragas_eval.py` → Faithfulness / Answer Relevancy / 回归耗时（见 `RAGAS_LLM_JUDGE.md`）
- 改进闭环说明：`eval/IMPROVEMENT_LOOP.md`（baseline → 定位 → 单点修改 → 重跑对比）

当前对外口径以 **`eval/METRICS_AUTHORITY.md`** 为准。

| 权威项 | 数字 |
|--------|------|
| 忠实度（同库，各 3 次） | 字段命中 **[0.844]→[0.969,1.000]**（区间不重叠） |
| Holdout 检索（16 条） | 原始 Hit@4 **0.75** → 通用 Rewrite **0.81** |
| 注入渗透（45 攻击 + 9 良性） | 拦截率 **1.000**；良性 **9/9** |
| 办理断言（单轮 32 + 多轮 20） | **49/52** |
| RAGAS+Judge（n=35） | Faith **0.62** / Rel **0.87** / Judge **0.63**；耗时 **2.3h→0.09h** |
| 失败构成（Holdout） | 原始 4 miss 均为成类新表述；干扰项全过 |

详见 `eval/HOLDOUT_ERROR_ANALYSIS.md`。

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
