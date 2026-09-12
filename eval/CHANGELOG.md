# Changelog（评测与知识库相关）

## 2026-09-13

### Faithfulness：`grad_cross_fee` forbid 调整

- **文件**：`eval/faithfulness_cases.json`
- **原 forbid**：含 `继续按150`
- **现 forbid**：`仍然150元`、`继续收150`、`0.29`
- **原因**：模型正确回答「不能继续按150元用了」时会被子串 `继续按150` 误判为幻觉（false positive）。收紧 forbid 只拦截「仍按150收费」类错误断言，不惩罚正确否定表述。
- **说明**：未删除该用例；`cross_switch_overage_oral` / `grad_cross_fee` 仍在集合中。

### Query Rewrite：特例规则 → 通用槽位归一化

- **文件**：`prompts/prompt_template_rewrite.txt`
- **变更**：去掉针对「当月改套餐 / 毕业+月费」的用例式硬编码规则；改为对象/动作/条件槽位抽取 + 模板组装；抽不全则回退原问题。
- **评测约束**：最终检索指标以 **holdout**（`eval/retrieval_cases_holdout.json`）为准；dev 仅用于定位与回归。

## 2026-09-13（续）

### Holdout 扩至 16 + 三组对照

- 原始 Hit@4=0.75；特例 Rewrite=1.00（类级补丁）；通用 Rewrite=0.81
- 失败构成：原始 4 miss 均为 same_class（转套餐/毕业），见 `HOLDOUT_ERROR_ANALYSIS.md`

### 忠实度 before/after 各连跑 3 次

- baseline agent：字段命中恒为 0.844（12/16）
- strong agent：字段命中 [0.969, 1.000]（14～15/16）
- **区间不重叠**，可报告有效改进
