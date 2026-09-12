# Holdout 失败构成分析（n=16）

## 三组对比

| 条件 | Hit@4 | MRR | 通过 |
|------|-------|-----|------|
| 原始 query（改前基线） | **0.750** | 0.688 | 12/16 |
| 特例 Rewrite（类级补丁） | 1.000 | 0.938 | 16/16 |
| 通用槽位 Rewrite（线上） | **0.812** | 0.641 | 13/16 |

解读：相对原始 **0.75→0.81**（通用改写有收益但未满分）；特例规则到 1.0 说明对「转套餐/毕业」两类问法有效，但是**类级硬编码**，简历勿当最终结论。

## 原始 query 失败 4 条（构成）

| id | kind | error_class | 结论 |
|----|------|-------------|------|
| `holdout_switch_immediate` | paraphrase | same_class_switch | 同类新表述，召回偏套餐名/受众 |
| `holdout_switch_oral2` | paraphrase | same_class_switch | 同上 |
| `holdout_grad_price` | paraphrase | same_class_grad | 同类新表述，未命中毕业转档+畅游价 |
| `holdout_grad_fee2` | paraphrase | same_class_grad | 同上 |

- **干扰项（distract）**：0 失败 → 不是主矛盾  
- **全新题型（new_topic）**：0 失败 → holdout 难度主要来自「成类改写」而非乱出题  
- **结论**：0.75 的缺口主要是 **同类新表述泛化不足**，与 dev 上定位的成类问题一致。

## 通用 Rewrite 后仍失败 3 条

仍为 `same_class_switch` / `same_class_grad`（`holdout_switch_immediate`、`holdout_grad_price`、`holdout_grad_fee2`）。  
`holdout_switch_oral2` 在通用改写下转 PASS。  

→ 通用归一化有部分泛化，但不足以覆盖全部同类新表述；后续若再调规则，须把失败题迁入 **dev**，并新写 holdout。
