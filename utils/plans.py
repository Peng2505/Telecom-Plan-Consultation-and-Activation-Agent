"""流量套餐权威价表与超套规则（与 knowledge/data_plans.md 保持一致）。"""
import json
from typing import Optional

PLANS = {
    "经济套餐": {
        "name": "经济套餐",
        "monthly_fee": 50,
        "quota_gb": 10,
        "campus_only": False,
        "summary": "月费50元，含10GB流量，适合轻度使用",
    },
    "畅游套餐": {
        "name": "畅游套餐",
        "monthly_fee": 180,
        "quota_gb": 100,
        "campus_only": False,
        "summary": "月费180元，含100GB流量，适合日常刷视频",
    },
    "无限套餐": {
        "name": "无限套餐",
        "monthly_fee": 300,
        "quota_gb": 1000,
        "campus_only": False,
        "summary": "月费300元，含1000GB流量，适合重度使用",
    },
    "校园套餐": {
        "name": "校园套餐",
        "monthly_fee": 150,
        "quota_gb": 200,
        "campus_only": True,
        "summary": "月费150元，含200GB流量，仅限在校生",
    },
}

# 超出套餐内流量后，每 GB 按 10 元计费，单月超套封顶 200 元
OVERAGE_PER_GB = 10
OVERAGE_CAP = 200


def overage_meta() -> dict:
    return {
        "overage_per_gb": OVERAGE_PER_GB,
        "overage_cap": OVERAGE_CAP,
        "overage_rule": f"超出部分每GB {OVERAGE_PER_GB} 元，单月超套封顶 {OVERAGE_CAP} 元",
    }


def _normalize_plan_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    text = name.strip()
    aliases = {
        "经济": "经济套餐",
        "便宜": "经济套餐",
        "最便宜": "经济套餐",
        "畅游": "畅游套餐",
        "无限": "无限套餐",
        "校园": "校园套餐",
        "学生": "校园套餐",
    }
    if text in PLANS:
        return text
    for key, value in aliases.items():
        if key in text:
            return value
    return None


def lookup_plan_data(query: str = "", campus_student: bool = False) -> dict:
    q = (query or "").strip()
    if "全部" in q or "所有" in q or "对比" in q or q == "":
        plans = list(PLANS.values())
        if not campus_student:
            plans = [p for p in plans if not p["campus_only"]] + [
                {**PLANS["校园套餐"], "note": "仅在校生可办理"}
            ]
        return {**overage_meta(), "plans": plans}

    name = _normalize_plan_name(q)
    if name:
        plan = dict(PLANS[name])
        if plan["campus_only"] and not campus_student:
            plan["eligibility"] = "仅限在校生，需提供学生证或在读证明"
        return {**overage_meta(), "plan": plan}

    if "最便宜" in q or "便宜" in q:
        return {**overage_meta(), "plan": PLANS["经济套餐"]}
    if "学生" in q or "校园" in q:
        return {**overage_meta(), "plan": PLANS["校园套餐"], "eligibility": "仅限在校生"}

    return {"error": "未识别套餐名", "available": list(PLANS.keys())}


def estimate_overage_data(monthly_usage_gb: float, current_plan: str) -> dict:
    name = _normalize_plan_name(current_plan)
    if not name:
        return {"error": "未知套餐", "available": list(PLANS.keys())}
    plan = PLANS[name]
    quota = plan["quota_gb"]
    extra = max(0.0, float(monthly_usage_gb) - quota)
    overage_fee = min(extra * OVERAGE_PER_GB, OVERAGE_CAP)
    total = plan["monthly_fee"] + overage_fee
    exceeded = extra > 0

    recommendation = name
    for candidate in ("经济套餐", "校园套餐", "畅游套餐", "无限套餐"):
        p = PLANS[candidate]
        if p["quota_gb"] >= monthly_usage_gb:
            recommendation = candidate
            break
    else:
        recommendation = "无限套餐"

    return {
        "current_plan": plan,
        "monthly_usage_gb": monthly_usage_gb,
        "exceeded": exceeded,
        "extra_gb": extra,
        "overage_fee": overage_fee,
        **overage_meta(),
        "estimated_total": total,
        "recommended_plan": PLANS[recommendation],
    }


def recommend_plan_data(monthly_usage_gb: float, campus_student: bool = False) -> dict:
    """按资格和用量返回满足流量需求且月费最低的套餐。"""
    usage = max(0.0, float(monthly_usage_gb))
    eligible = [
        plan for plan in PLANS.values()
        if (campus_student or not plan["campus_only"]) and plan["quota_gb"] >= usage
    ]
    if eligible:
        recommended = min(eligible, key=lambda p: (p["monthly_fee"], p["quota_gb"]))
    else:
        allowed = [
            plan for plan in PLANS.values()
            if campus_student or not plan["campus_only"]
        ]
        recommended = max(allowed, key=lambda p: p["quota_gb"])
    remaining = max(0.0, recommended["quota_gb"] - usage)
    return {
        "monthly_usage_gb": usage,
        "campus_student": campus_student,
        "recommended_plan": recommended,
        "remaining_gb": remaining,
        "utilization_percent": round(usage / recommended["quota_gb"] * 100, 1),
        "reason": "在符合资格且覆盖月用量的套餐中选择月费最低方案",
        **overage_meta(),
    }


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
