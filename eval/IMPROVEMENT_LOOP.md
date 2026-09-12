# 分层评测改进闭环（baseline → 定位 → 单点修改 → 回归对比）

目标：用指标驱动改进，而不是只堆数字。一次只改一处，固定同一用例集对比。

## 1. 先跑 baseline

知识库有变更或首次启用稳定 chunk id 后，先重建向量库：

```bat
cd /d d:\LangGraphChatBot-main\04_RagAgent
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

说明：知识库很小，检索分数可能偏高；通过口语化 / 跨节 / 干扰名 / 应拒答加难后才有区分度。指标用于小样本回归与改进归因，不是大规模公开榜。

## 5. 一次真实对比（加难用例后）

固定用例集：检索 26 条、忠实度 16 条。线上检索与评测均取 **Top-4**（`Config.RETRIEVAL_TOP_K`，简历写 Hit@4）。

| 指标 | baseline（加难后） | after_fix（只改 agent 提示词） |
|------|-------------------|--------------------------------|
| Hit@4 | 1.000（26/26；K=3 时曾为 0.962，口语转套餐排第 4 才命中） | 未改检索 |
| MRR | **0.907** | 未改检索 |
| 字段命中率 | 0.844 | **0.969** |
| 数字幻觉率 | 0.062 | **0.000** |
| 忠实度用例 | 12/16 | **14/16** |

定位：`refuse_employee_discount` / `refuse_portability` 未走边界拒答；`grad_cross_fee` 与跨节口语问法出现编造价格、漏说账期约束。

单点修改：`prompts/prompt_template_agent.txt`——强制未文档化政策 `retrieve_plans` 后「无法确认，请到营业厅核实」；提到畅游/月费必须 `lookup_plan`；转套餐+超套组合问必须检索转套餐规则。

仍失败（可继续迭代）：`cross_switch_overage_oral`（账期表述）、`grad_cross_fee`（偶发编造月费）。诚实保留，不改用例凑分。

说明：Hit@4 在粗库上易顶满；细粒度 `policy_v2`（31 chunk）重标后 Hit/MRR 下降是预期，应用 MRR 与失败用例讲改进故事。面试主动说明线上与评测均为 Top-4。

## 6. 知识库拆细后的检索对比（policy_v2）

线上已切换为 `policy_v2`（`CHROMADB_COLLECTION_NAME=policy_v2`）。旧集合 `data_plans` 可回滚。

| 指标 | 粗库 data_plans（11 chunk） | 细库 policy_v2（31 chunk，已重标） |
|------|------------------------------|-------------------------------------|
| Hit@4 | 1.000（26/26） | **0.923（24/26）** → 扩用例后原始检索 **0.935（29/31）** |
| MRR | 0.907 | **0.885** → 扩用例后 **0.903** |
| K/库 | 4/11≈36% | 4/31≈13% |
| 失败用例（成类） | — | 口语「套餐名+当月改」、跨节「毕业+月费」 |

## 7. 第三张对比表：Query Rewrite 单点修复

成类问题确认后，只改 `prompts/prompt_template_rewrite.txt`（转套餐账期 / 毕业转畅游+月费）。评测：`run_retrieval_eval.py --with-rewrite`。

| 指标 | 原始 query 检索（扩用例 31 条） | 先 Rewrite 再检索 |
|------|-------------------------------|-------------------|
| Hit@4 | **0.935（29/31）** | **1.000（31/31）** |
| MRR | **0.903** | **0.984** |
| 原失败 | `oral_switch_named`, `cross_grad_fee` | 均命中 |

产物：`last_retrieval_result_before_rewrite.json` / `last_retrieval_result_after_rewrite.json`。
