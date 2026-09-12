# 分层评测改进闭环（baseline → 定位 → 单点修改 → 回归对比）

目标：用指标驱动改进，而不是只堆数字。一次只改一处，固定同一用例集对比。

## 1. 先跑 baseline

知识库有变更或首次启用稳定 chunk id 后，先重建向量库：

```bat
cd /d D:\data-plan-langgraph-agent
D:\Anaconda\envs\langgraph\python.exe vectorSaveTest.py
```

只测检索（不需要 API）：

```bat
D:\Anaconda\envs\langgraph\python.exe eval\run_retrieval_eval.py
```

完整分层（需要 `main.py` 已启动）：

```bat
D:\Anaconda\envs\langgraph\python.exe eval\run_all.py --label baseline
```

产物：

- `eval/last_retrieval_result.json`：Hit@K、MRR、失败用例
- `eval/last_faithfulness_result.json`：字段命中率、数字幻觉率
- `eval/last_eval_summary_baseline.json`：汇总表

## 2. 挑 1 个低分用例

优先看：

- 检索 `failed_ids`：哪条 query 没命中 `relevant_ids`
- 忠实度 `failed_ids`：缺了哪个 must_include，或踩了哪个 forbid（如 `0.29`）

## 3. 定位根因

| 现象 | 可能根因 | 改哪里 |
|------|----------|--------|
| 检索 miss | 分块边界、标题表述、Top-K 太小 | `knowledge/data_plans.md` 或 `RETRIEVAL_TOP_K` |
| 数字说错 | 模型口算、未调工具、提示词约束弱 | `prompts/` 或工具路由 |
| 虚假开通 | 确认/业支约束失效 | `demoRagAgent.py` / `orders.py` / `bss_mock.py` |

## 4. 只改一处后重跑

```bat
D:\Anaconda\envs\langgraph\python.exe eval\run_all.py --label after_fix
```

对比 `last_eval_summary_baseline.json` 与 `last_eval_summary_after_fix.json`。

不要在同一次改动里同时改用例集和代码，否则无法归因。

## 指标定义（简历可用）

- **Hit Rate@K**：Top-K 是否命中任一标注相关 chunk
- **MRR**：第一条相关 chunk 排名的倒数平均
- **字段命中率**：回答命中 must_include 的比例
- **数字幻觉率**：出现 forbid 错误数字/虚假开通话术的用例比例

说明：当前知识库很小，Hit Rate 可能偏高；指标用于小样本回归与改进闭环，不是大规模公开榜单。

