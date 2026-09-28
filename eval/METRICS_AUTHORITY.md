# 评测指标权威表（对外口径以此为准）

> 最后更新：2026-09-28  
> 路径：`04_RagAgent/eval/`  
> **禁止**把「定位集上调参后的满分」或「未标注环境的两个忠实度数字」混写成一句结论。

## 1. 权威数字（按优先级）

### A. 简历主故事：同库 agent 提示词（报区间，区间不重叠）

| 条件 | 字段命中率区间（3 次） | 通过数区间 | 产物 |
|------|------------------------|------------|------|
| baseline agent | **[0.844, 0.844]** | **12～12 / 16** | `last_faithfulness_range_baseline_agent.json` |
| strong agent（强化边界/lookup） | **[0.969, 1.000]** | **14～15 / 16** | `last_faithfulness_range_strong_agent.json` |

- 提升约 **+0.125**；与「2/16=0.125 噪声」同量级，但 **before/after 区间不重叠** → 可报告为有效改进。  
- 单点改动：`prompt_template_agent.txt`（对照 `prompt_template_agent_baseline_legacy.txt`）。  
- 环境：同一套 `faithfulness_cases.json`、同一 `policy_v2` 线上集合。

### B. Holdout 检索（n=16，未参与调参）

| 条件 | Hit@4 | MRR | 通过 | 产物 |
|------|-------|-----|------|------|
| **原始 query（改前）** | **0.750** | 0.688 | 12/16 | `last_retrieval_holdout_raw.json` |
| 通用槽位 Rewrite（线上） | **0.812** | 0.641 | 13/16 | `last_retrieval_holdout_rewrite.json` |
| 特例类级 Rewrite（对照，不作最终） | 1.000 | 0.938 | 16/16 | `last_retrieval_holdout_special_rewrite.json` |

- 对外写：**Holdout 原始 0.75 → 通用 Rewrite 0.81**。  
- 特例 1.0 仅说明「类级硬编码对同类改述有效」，**不作简历最终结论**（易被视作过拟合）。  
- 失败构成见 `HOLDOUT_ERROR_ANALYSIS.md`：4 个原始失败全是 **same_class**（转套餐/毕业类新表述）；干扰项与新题型未拖后腿。

### C. 配置

| 项 | 值 |
|----|-----|
| 集合 / Top-K / chunk | `policy_v2` / **4** / **31** |
| K/库 | ≈13% |
| holdout / dev | `retrieval_cases_holdout.json`（16）/ `retrieval_cases_dev.json`（31） |

## 2. 作废 / 勿混写

| 数字 | 原因 |
|------|------|
| Hit@4=1.00（dev 同集 + 特例 Rewrite） | 测试集污染 |
| 粗库「0.844→0.969」与细库「13～15/16」写在同一句不标注阶段 | 读者以为最终掉到 0.81 |
| 只报 Holdout=0.75 不报改前 | 无法解读 Rewrite 是否有效（现已补齐：改前=原始 0.75） |

## 3. 忠实度「两套数字」怎么说

必须分阶段：

1. **同库对照（主故事）**：baseline→strong，字段命中 **[0.844]→[0.969,1.000]**（区间不重叠）。  
2. **波动观察**：strong 连跑通过 **14～15/16**（承认 LLM 波动，不报单次 16/16）。

不要再把早期「粗库单次 0.969」与「细库连跑下限」并成一句不解释。

## 4. Prompt 注入拦截率（2026-09-28 实测）

| 项 | 值 |
|----|-----|
| 攻击用例 | 16 |
| 拦截 | **16/16** |
| **interception_rate** | **1.000** |
| 良性对照 | 2/2 通过（问价/推荐未误杀） |
| 产物 | `last_injection_result.json` |

实现：提示词隔离标注 + 检索/工具包装 + 办理硬通道拒注入（`INJECTION_GUARDRAILS.md` / `utils/guardrails.py`）。

## 5. RAGAS 对齐 + LLM-as-Judge + 回归耗时（2026-09-28 实测）

| 项 | 值 |
|----|-----|
| 用例 n | 14（`ragas_cases.json`） |
| backend | `llm_aligned_fallback`（ragas 0.4.3 与当前 LangChain 导入冲突，指标定义对齐 RAGAS） |
| **faithfulness** | **0.714** |
| **answer_relevancy** | **0.900** |
| **judge_pass_rate** | **0.571** |
| 手工估算耗时 | **0.93 h**（14×4min） |
| 自动墙钟 | **0.036 h**（约 2.2 min） |
| 产物 | `last_ragas_result.json` / `last_eval_timing.json` |

与 rules 忠实度（must_include/forbid）**并列**，不互相替换。Judge 更严（含业务安全），故 pass rate 可低于 Answer Relevancy。

## 6. 简历推荐表述（与上表一致）

> 自建分层评测（holdout 检索 + 工具忠实度）。强化 agent 提示词后，字段命中率由 **0.844** 提升至 **0.97～1.00**（各连跑 3 次，区间不重叠）。政策库 31 chunk、Top-4；Query Rewrite 为对象-动作-条件通用归一化。Holdout（16 条）原始 Hit@4=**0.75**，通用改写后 **0.81**；失败均为成类新表述，干扰项未拖累。

> Prompt 注入防御与 Guardrails：用户输入与检索文档隔离标注，办理高危指令走独立二次确认通道；自建渗透集（16 条攻击）拦截率 **100%**，良性问价/推荐 2/2 未误杀。

> 引入 RAGAS 对齐的 Faithfulness / Answer Relevancy（实测 **0.71 / 0.90**）与 LLM-as-Judge 自动回归；同类 14 条用例回归耗时由手工估算约 **0.93h** 降至自动约 **0.04h**。

## 7. 复现命令

```bat
cd /d d:\LangGraphChatBot-main\04_RagAgent
set EVAL_CHROMA_COLLECTION=policy_v2

python eval\run_retrieval_eval.py --cases retrieval_cases_holdout.json --out last_retrieval_holdout_raw.json
copy /Y prompts\prompt_template_rewrite_generic.txt prompts\prompt_template_rewrite.txt
python eval\run_retrieval_eval.py --cases retrieval_cases_holdout.json --with-rewrite --out last_retrieval_holdout_rewrite.json

REM 忠实度区间：先 baseline_legacy agent，再 strong agent，各：
python eval\run_faithfulness_range.py 3

REM 注入 + RAGAS（需 API）
python eval\run_injection_eval.py
python eval\run_ragas_eval.py
REM 或：python eval\run_all.py --label full --with-injection --with-ragas
```

## 8. 相关文件

- `CHANGELOG.md` / `HOLDOUT_ERROR_ANALYSIS.md` / `INJECTION_GUARDRAILS.md` / `RAGAS_LLM_JUDGE.md`
- `prompt_template_rewrite_generic.txt` / `prompt_template_rewrite_special_legacy.txt`  
- `prompt_template_agent_strong.txt` / `prompt_template_agent_baseline_legacy.txt`
- `utils/guardrails.py`
