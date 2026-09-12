"""套餐知识库切分与稳定 chunk id（入库与检索评测共用）。"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# 标题 -> 稳定 id（评测标注依赖这些 id，勿随意改名）
# 含 data_plans.md（粗粒度）与 data_plans_v2.md（细粒度）
HEADING_TO_ID = {
    # v1
    "经济套餐": "economy_plan",
    "畅游套餐": "changyou_plan",
    "无限套餐": "unlimited_plan",
    "校园套餐": "campus_plan",
    "超套计费规则": "overage_rule",
    "流量是否当月清零": "rollover_rule",
    "能否转套餐": "change_plan_rule",
    "校园如何认证": "campus_verify",
    "多卡与副卡": "multi_sim",
    "夜间加速": "night_boost",
    "客服边界": "support_boundary",
    # v2
    "经济套餐月费与流量": "economy_fee_quota",
    "经济套餐适用场景": "economy_audience",
    "经济套餐无校园限制": "economy_no_campus_gate",
    "畅游套餐月费与流量": "changyou_fee_quota",
    "畅游套餐适用场景": "changyou_audience",
    "无限套餐月费与流量": "unlimited_fee_quota",
    "无限套餐适用场景": "unlimited_audience",
    "无限套餐名称含义": "unlimited_meaning",
    "校园套餐月费与流量": "campus_fee_quota",
    "校园套餐办理资格": "campus_eligibility",
    "超套计费与封顶": "overage_billing",
    "超套优先升档建议": "overage_prefer_upgrade",
    "超套试算以工具为准": "overage_tool_authority",
    "流量按自然月计费": "billing_cycle_natural_month",
    "流量不结转下月": "rollover_no_carry",
    "转套餐账期规则": "change_plan_timing",
    "校园套餐转出后不可转回": "change_plan_campus_return",
    "校园认证材料与生效": "campus_verify_docs",
    "毕业后自动转畅游": "campus_graduate_convert",
    "主卡可办四档套餐": "multi_sim_main_options",
    "副卡共享流量无独立价": "multi_sim_share_no_independent_price",
    "无未公示亲情号折扣": "multi_sim_no_undoc_family_discount",
    "夜间不赠送不加速": "night_no_bonus",
    "客服只答知识库与价表": "support_answer_scope",
    "未文档化折扣需营业厅核实": "support_refuse_undoc_discount",
    "内部员工套餐需营业厅核实": "support_refuse_employee_plan",
    "携号转网赔偿需营业厅核实": "support_refuse_mnp",
    "禁止编造价格": "support_no_invent_price",
    "官方套餐名称仅四档": "official_plan_names",
    "不存在校园畅学套餐": "alias_reject_campus_changxue",
    "不存在畅享套餐": "alias_reject_changxiang",
}

# chunk_id -> 元数据（入库写入 Chroma metadata）
CHUNK_METADATA: Dict[str, Dict[str, str]] = {
    "economy_fee_quota": {"policy_category": "plan", "plan_scope": "economy"},
    "economy_audience": {"policy_category": "plan", "plan_scope": "economy"},
    "economy_no_campus_gate": {"policy_category": "eligibility", "plan_scope": "economy"},
    "changyou_fee_quota": {"policy_category": "plan", "plan_scope": "changyou"},
    "changyou_audience": {"policy_category": "plan", "plan_scope": "changyou"},
    "unlimited_fee_quota": {"policy_category": "plan", "plan_scope": "unlimited"},
    "unlimited_audience": {"policy_category": "plan", "plan_scope": "unlimited"},
    "unlimited_meaning": {"policy_category": "plan", "plan_scope": "unlimited"},
    "campus_fee_quota": {"policy_category": "plan", "plan_scope": "campus"},
    "campus_eligibility": {"policy_category": "eligibility", "plan_scope": "campus"},
    "overage_billing": {"policy_category": "billing", "plan_scope": "all"},
    "overage_prefer_upgrade": {"policy_category": "billing", "plan_scope": "all"},
    "overage_tool_authority": {"policy_category": "billing", "plan_scope": "all"},
    "billing_cycle_natural_month": {"policy_category": "billing", "plan_scope": "all"},
    "rollover_no_carry": {"policy_category": "billing", "plan_scope": "all"},
    "change_plan_timing": {"policy_category": "process", "plan_scope": "all"},
    "change_plan_campus_return": {"policy_category": "process", "plan_scope": "campus"},
    "campus_verify_docs": {"policy_category": "process", "plan_scope": "campus"},
    "campus_graduate_convert": {"policy_category": "process", "plan_scope": "campus"},
    "multi_sim_main_options": {"policy_category": "plan", "plan_scope": "all"},
    "multi_sim_share_no_independent_price": {"policy_category": "plan", "plan_scope": "all"},
    "multi_sim_no_undoc_family_discount": {"policy_category": "boundary", "plan_scope": "all"},
    "night_no_bonus": {"policy_category": "billing", "plan_scope": "all"},
    "support_answer_scope": {"policy_category": "boundary", "plan_scope": "n/a"},
    "support_refuse_undoc_discount": {"policy_category": "boundary", "plan_scope": "n/a"},
    "support_refuse_employee_plan": {"policy_category": "boundary", "plan_scope": "n/a"},
    "support_refuse_mnp": {"policy_category": "boundary", "plan_scope": "n/a"},
    "support_no_invent_price": {"policy_category": "boundary", "plan_scope": "n/a"},
    "official_plan_names": {"policy_category": "alias", "plan_scope": "all"},
    "alias_reject_campus_changxue": {"policy_category": "alias", "plan_scope": "campus"},
    "alias_reject_changxiang": {"policy_category": "alias", "plan_scope": "changyou"},
    # v1 粗粒度（兼容旧集合）
    "economy_plan": {"policy_category": "plan", "plan_scope": "economy"},
    "changyou_plan": {"policy_category": "plan", "plan_scope": "changyou"},
    "unlimited_plan": {"policy_category": "plan", "plan_scope": "unlimited"},
    "campus_plan": {"policy_category": "plan", "plan_scope": "campus"},
    "overage_rule": {"policy_category": "billing", "plan_scope": "all"},
    "rollover_rule": {"policy_category": "billing", "plan_scope": "all"},
    "change_plan_rule": {"policy_category": "process", "plan_scope": "all"},
    "campus_verify": {"policy_category": "process", "plan_scope": "campus"},
    "multi_sim": {"policy_category": "plan", "plan_scope": "all"},
    "night_boost": {"policy_category": "billing", "plan_scope": "all"},
    "support_boundary": {"policy_category": "boundary", "plan_scope": "n/a"},
}

# 粗 chunk -> 细 chunk（8.3 重标映射用）
V1_TO_V2_IDS: Dict[str, List[str]] = {
    "economy_plan": ["economy_fee_quota", "economy_audience", "economy_no_campus_gate"],
    "changyou_plan": ["changyou_fee_quota", "changyou_audience"],
    "unlimited_plan": ["unlimited_fee_quota", "unlimited_audience", "unlimited_meaning"],
    "campus_plan": ["campus_fee_quota", "campus_eligibility"],
    "overage_rule": ["overage_billing", "overage_prefer_upgrade", "overage_tool_authority"],
    "rollover_rule": ["billing_cycle_natural_month", "rollover_no_carry"],
    "change_plan_rule": ["change_plan_timing", "change_plan_campus_return"],
    "campus_verify": ["campus_verify_docs", "campus_graduate_convert"],
    "multi_sim": [
        "multi_sim_main_options",
        "multi_sim_share_no_independent_price",
        "multi_sim_no_undoc_family_discount",
    ],
    "night_boost": ["night_no_bonus"],
    "support_boundary": [
        "support_answer_scope",
        "support_refuse_undoc_discount",
        "support_refuse_employee_plan",
        "support_refuse_mnp",
        "support_no_invent_price",
    ],
}


def _slug_fallback(heading: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", heading.strip(), flags=re.UNICODE)
    slug = slug.strip("_").lower() or "chunk"
    return slug[:64]


def split_markdown_sections(text: str) -> List[Tuple[str, str]]:
    """按二级标题切分，返回 [(chunk_id, document), ...]。"""
    sections: List[Tuple[str, str]] = []
    current_heading = ""
    current_lines: List[str] = []

    def flush():
        nonlocal current_heading, current_lines
        body = "\n".join(current_lines).strip()
        if not body or not current_heading:
            current_lines = []
            return
        chunk_id = HEADING_TO_ID.get(current_heading, _slug_fallback(current_heading))
        sections.append((chunk_id, body))
        current_lines = []

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            current_lines = [line]
        else:
            if current_heading:
                current_lines.append(line)
    flush()
    return sections


def metadata_for_chunk(chunk_id: str, source: str) -> Dict[str, str]:
    meta = dict(CHUNK_METADATA.get(chunk_id, {"policy_category": "unknown", "plan_scope": "n/a"}))
    meta["chunk_id"] = chunk_id
    meta["source"] = source
    return meta


def load_knowledge_chunks(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return split_markdown_sections(text)
