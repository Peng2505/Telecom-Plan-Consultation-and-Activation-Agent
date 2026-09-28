# RAGAS 对齐指标 + LLM-as-Judge

## 说明

- 脚本：`eval/run_ragas_eval.py`
- 用例：`eval/ragas_cases.json`（14 条）
- 产物：`eval/last_ragas_result.json`、`eval/last_eval_timing.json`

优先尝试官方 `ragas` 库；若与当前 LangChain 不兼容，自动回退为 **同定义的 LLM 评分**（Faithfulness / Answer Relevancy），并在结果 JSON 的 `backend` 字段标明 `llm_aligned_fallback`。

LLM-as-Judge 始终运行：`score_1_to_5`、`policy_safe`、`pass`。

## 回归耗时

- **手工估算**：`N × EVAL_MANUAL_MINUTES_PER_CASE（默认 4）/ 60` 小时  
- **自动**：脚本墙钟时间  

## 复现

```bat
cd /d d:\LangGraphChatBot-main\04_RagAgent
REM 需 API 已启动且 .env 有 DASHSCOPE_API_KEY
D:\Anaconda\envs\langgraph\python.exe eval\run_ragas_eval.py
```

或：

```bat
D:\Anaconda\envs\langgraph\python.exe eval\run_all.py --label full --with-injection --with-ragas
```
