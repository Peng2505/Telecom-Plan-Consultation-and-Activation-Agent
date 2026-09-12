# Retrieval relevant_ids 重标 Review（policy_v2）

生成方式：`python eval/build_relabel_review.py`

- **自动展开**：旧粗 chunk → 其全部子 chunk（可能偏宽）
- **建议 gold**：按问句意图收紧后的标注（请逐条确认）
- 默认**不覆盖** `retrieval_cases.json`；确认后加 `--apply` 写回建议列

## 全表

| 用例 id | 原 relevant_ids | 自动展开 | 建议的新 relevant_ids | 问题原文 |
|---------|-----------------|----------|----------------------|----------|
| `campus_who` | `campus_plan` | `campus_fee_quota, campus_eligibility` | `campus_eligibility` | 校园套餐给谁用 |
| `overage_how` | `overage_rule` | `overage_billing, overage_prefer_upgrade, overage_tool_authority` | `overage_billing` | 超出套餐流量怎么收费 |
| `rollover` | `rollover_rule` | `billing_cycle_natural_month, rollover_no_carry` | `rollover_no_carry` | 流量没用完能转到下个月吗 |
| `change_plan_when` | `change_plan_rule` | `change_plan_timing, change_plan_campus_return` | `change_plan_timing` | 这个月能不能马上改套餐 |
| `campus_verify` | `campus_verify, campus_plan` | `campus_verify_docs, campus_graduate_convert, campus_fee_quota, campus_eligibility` | `campus_verify_docs, campus_eligibility` | 校园套餐怎么做学生认证 |
| `multi_sim` | `multi_sim` | `multi_sim_main_options, multi_sim_share_no_independent_price, multi_sim_no_undoc_family_discount` | `multi_sim_share_no_independent_price` | 副卡有没有独立套餐价 |
| `night_boost` | `night_boost` | `night_no_bonus` | `night_no_bonus` | 夜间会不会额外送流量 |
| `support_boundary` | `support_boundary` | `support_answer_scope, support_refuse_undoc_discount, support_refuse_employee_plan, support_refuse_mnp, support_no_invent_price` | `support_refuse_employee_plan` | 内部员工套餐有没有折扣 |
| `unlimited_meaning` | `unlimited_plan` | `unlimited_fee_quota, unlimited_audience, unlimited_meaning` | `unlimited_meaning` | 无限套餐是不是绝对不限量 |
| `oral_student_50g` | `campus_plan` | `campus_fee_quota, campus_eligibility` | `campus_fee_quota` | 我学生卡，一个月刷50个G够不够用？ |
| `oral_overage_cap` | `overage_rule` | `overage_billing, overage_prefer_upgrade, overage_tool_authority` | `overage_billing` | 流量超了按啥收费啊，封顶没有 |
| `oral_night_free` | `night_boost` | `night_no_bonus` | `night_no_bonus` | 晚上有没有白嫖流量 |
| `oral_rollover` | `rollover_rule` | `billing_cycle_natural_month, rollover_no_carry` | `rollover_no_carry` | 剩的流量下个月还能接着用吗 |
| `oral_sim_cheap` | `multi_sim` | `multi_sim_main_options, multi_sim_share_no_independent_price, multi_sim_no_undoc_family_discount` | `multi_sim_share_no_independent_price` | 副卡能不能单独办个五十块的 |
| `oral_switch_named` | `change_plan_rule` | `change_plan_timing, change_plan_campus_return` | `change_plan_timing` | 这个月能不能把经济换成畅游 |
| `oral_switch_named2` | `change_plan_rule` | `change_plan_timing, change_plan_campus_return` | `change_plan_timing` | 经济套餐换成畅游套餐，当月能立刻改吗 |
| `cross_grad_fee` | `campus_verify, changyou_plan` | `campus_verify_docs, campus_graduate_convert, changyou_fee_quota, changyou_audience` | `campus_graduate_convert, changyou_fee_quota` | 毕业了校园套餐还能不能用，月费变多少 |
| `cross_switch_overage` | `change_plan_rule, overage_rule` | `change_plan_timing, change_plan_campus_return, overage_billing, overage_prefer_upgrade, overage_tool_authority` | `change_plan_timing, overage_billing` | 这个月从经济改畅游行不行，不行的话超套怎么收 |
| `cross_student_overage` | `campus_plan, overage_rule` | `campus_fee_quota, campus_eligibility, overage_billing, overage_prefer_upgrade, overage_tool_authority` | `campus_fee_quota, overage_billing` | 学生卡刷50G，校园那个200G够不够，超了咋办 |
| `distract_changxue` | `campus_plan, support_boundary` | `campus_fee_quota, campus_eligibility, support_answer_scope, support_refuse_undoc_discount, support_refuse_employee_plan, support_refuse_mnp, support_no_invent_price` | `alias_reject_campus_changxue, campus_fee_quota, official_plan_names` | 校园畅学套餐和校园套餐是不是一个东西 |
| `distract_youxiang` | `changyou_plan` | `changyou_fee_quota, changyou_audience` | `alias_reject_changxiang, changyou_fee_quota` | 畅享套餐和畅游套餐哪个贵 |
| `refuse_portability` | `support_boundary` | `support_answer_scope, support_refuse_undoc_discount, support_refuse_employee_plan, support_refuse_mnp, support_no_invent_price` | `support_refuse_mnp` | 携号转网能赔多少钱 |
| `refuse_undoc_discount` | `multi_sim, support_boundary` | `multi_sim_main_options, multi_sim_share_no_independent_price, multi_sim_no_undoc_family_discount, support_answer_scope, support_refuse_undoc_discount, support_refuse_employee_plan, support_refuse_mnp, support_no_invent_price` | `multi_sim_no_undoc_family_discount, support_refuse_undoc_discount` | 有没有未公示的亲情号折扣 |
| `nonstudent_200g` | `campus_plan` | `campus_fee_quota, campus_eligibility` | `campus_eligibility` | 我没学生证能办那个200G的吗 |
| `billing_oral` | `rollover_rule` | `billing_cycle_natural_month, rollover_no_carry` | `billing_cycle_natural_month` | 算账是按自然月还是按30天 |
| `long_overage_oral` | `overage_rule` | `overage_billing, overage_prefer_upgrade, overage_tool_authority` | `overage_prefer_upgrade, overage_billing` | 老是超量是不是该换大一点的套餐 |

## 多 gold / 跨节用例（需重点人工确认）

下列用例建议的新 `relevant_ids` **多于 1 个**，或跨越多个原粗 chunk / 含 alias：

- **campus_verify**（跨节 / 多gold×2）：`campus_verify_docs, campus_eligibility` — 校园套餐怎么做学生认证
- **cross_grad_fee**（跨节 / 多gold×2）：`campus_graduate_convert, changyou_fee_quota` — 毕业了校园套餐还能不能用，月费变多少
- **cross_switch_overage**（跨节 / 多gold×2）：`change_plan_timing, overage_billing` — 这个月从经济改畅游行不行，不行的话超套怎么收
- **cross_student_overage**（跨节 / 多gold×2）：`campus_fee_quota, overage_billing` — 学生卡刷50G，校园那个200G够不够，超了咋办
- **distract_changxue**（跨节 / 多gold×3）：`alias_reject_campus_changxue, campus_fee_quota, official_plan_names` — 校园畅学套餐和校园套餐是不是一个东西
- **distract_youxiang**（跨节 / 多gold×2）：`alias_reject_changxiang, changyou_fee_quota` — 畅享套餐和畅游套餐哪个贵
- **refuse_undoc_discount**（跨节 / 多gold×2）：`multi_sim_no_undoc_family_discount, support_refuse_undoc_discount` — 有没有未公示的亲情号折扣
- **long_overage_oral**（多gold×2）：`overage_prefer_upgrade, overage_billing` — 老是超量是不是该换大一点的套餐

## 统计

- 用例总数：26
- 建议为多 gold 或跨节：8 条 → `campus_verify, cross_grad_fee, cross_switch_overage, cross_student_overage, distract_changxue, distract_youxiang, refuse_undoc_discount, long_overage_oral`

## 确认后写回

```bat
D:\Anaconda\envs\langgraph\python.exe eval\build_relabel_review.py --apply
```

