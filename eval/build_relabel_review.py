"""将 retrieval_cases 的旧 relevant_ids 映射到 v2 细粒度 id，并写出人工 review 清单。

默认只生成 eval/relabel_review.md，不覆盖 retrieval_cases.json。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.knowledge import V1_TO_V2_IDS  # noqa: E402

EVAL = Path(__file__).resolve().parent
CASES_PATH = EVAL / "retrieval_cases.json"
REVIEW_PATH = EVAL / "relabel_review.md"

# 按问题意图收紧后的建议 gold（供人工确认；可比自动展开更窄）
SUGGESTED_BY_CASE: dict[str, list[str]] = {
    "campus_who": ["campus_eligibility"],
    "overage_how": ["overage_billing"],
    "rollover": ["rollover_no_carry"],
    "change_plan_when": ["change_plan_timing"],
    "campus_verify": ["campus_verify_docs", "campus_eligibility"],
    "multi_sim": ["multi_sim_share_no_independent_price"],
    "night_boost": ["night_no_bonus"],
    "support_boundary": ["support_refuse_employee_plan"],
    "unlimited_meaning": ["unlimited_meaning"],
    "oral_student_50g": ["campus_fee_quota"],
    "oral_overage_cap": ["overage_billing"],
    "oral_night_free": ["night_no_bonus"],
    "oral_rollover": ["rollover_no_carry"],
    "oral_sim_cheap": ["multi_sim_share_no_independent_price"],
    "oral_switch_named": ["change_plan_timing"],
    "oral_switch_named2": ["change_plan_timing"],
    "cross_grad_fee": ["campus_graduate_convert", "changyou_fee_quota"],
    "cross_switch_overage": ["change_plan_timing", "overage_billing"],
    "cross_student_overage": ["campus_fee_quota", "overage_billing"],
    "distract_changxue": ["alias_reject_campus_changxue", "campus_fee_quota", "official_plan_names"],
    "distract_youxiang": ["alias_reject_changxiang", "changyou_fee_quota"],
    "refuse_portability": ["support_refuse_mnp"],
    "refuse_undoc_discount": [
        "multi_sim_no_undoc_family_discount",
        "support_refuse_undoc_discount",
    ],
    "nonstudent_200g": ["campus_eligibility"],
    "billing_oral": ["billing_cycle_natural_month"],
    "long_overage_oral": ["overage_prefer_upgrade", "overage_billing"],
}


def expand_v1_ids(old_ids: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for oid in old_ids:
        children = V1_TO_V2_IDS.get(oid, [oid])
        for cid in children:
            if cid not in seen:
                seen.add(cid)
                out.append(cid)
    return out


def parent_sections(chunk_ids: list[str]) -> set[str]:
    parents = set()
    for pid, children in V1_TO_V2_IDS.items():
        for cid in chunk_ids:
            if cid in children:
                parents.add(pid)
    # alias 等不在 V1 映射里
    for cid in chunk_ids:
        if cid.startswith("alias_") or cid == "official_plan_names":
            parents.add("__alias__")
    return parents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="确认后用 SUGGESTED_BY_CASE 写回 retrieval_cases.json（默认不写）",
    )
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows = []
    multi_gold = []

    for case in cases:
        cid = case["id"]
        old = case["relevant_ids"]
        auto = expand_v1_ids(old)
        suggested = SUGGESTED_BY_CASE.get(cid, auto)
        parents = parent_sections(suggested)
        is_multi = len(suggested) > 1
        is_cross_section = len(parents - {"__alias__"}) > 1 or (
            "__alias__" in parents and len(parents) > 1
        )
        rows.append(
            {
                "id": cid,
                "query": case["query"],
                "old": old,
                "auto": auto,
                "suggested": suggested,
                "is_multi": is_multi,
                "is_cross_section": is_cross_section,
            }
        )
        if is_multi or is_cross_section:
            multi_gold.append(cid)

    lines = [
        "# Retrieval relevant_ids 重标 Review（policy_v2）",
        "",
        "生成方式：`python eval/build_relabel_review.py`",
        "",
        "- **自动展开**：旧粗 chunk → 其全部子 chunk（可能偏宽）",
        "- **建议 gold**：按问句意图收紧后的标注（请逐条确认）",
        "- 默认**不覆盖** `retrieval_cases.json`；确认后加 `--apply` 写回建议列",
        "",
        "## 全表",
        "",
        "| 用例 id | 原 relevant_ids | 自动展开 | 建议的新 relevant_ids | 问题原文 |",
        "|---------|-----------------|----------|----------------------|----------|",
    ]
    for r in rows:
        lines.append(
            "| `{id}` | `{old}` | `{auto}` | `{sug}` | {q} |".format(
                id=r["id"],
                old=", ".join(r["old"]),
                auto=", ".join(r["auto"]),
                sug=", ".join(r["suggested"]),
                q=r["query"].replace("|", "\\|"),
            )
        )

    lines.extend(
        [
            "",
            "## 多 gold / 跨节用例（需重点人工确认）",
            "",
            "下列用例建议的新 `relevant_ids` **多于 1 个**，或跨越多个原粗 chunk / 含 alias：",
            "",
        ]
    )
    for r in rows:
        if not (r["is_multi"] or r["is_cross_section"]):
            continue
        tag = []
        if r["is_cross_section"]:
            tag.append("跨节")
        if r["is_multi"]:
            tag.append(f"多gold×{len(r['suggested'])}")
        lines.append(
            f"- **{r['id']}**（{' / '.join(tag)}）：`{', '.join(r['suggested'])}` — {r['query']}"
        )

    lines.extend(
        [
            "",
            "## 统计",
            "",
            f"- 用例总数：{len(rows)}",
            f"- 建议为多 gold 或跨节：{len(multi_gold)} 条 → `{', '.join(multi_gold)}`",
            "",
            "## 确认后写回",
            "",
            "```bat",
            "D:\\Anaconda\\envs\\langgraph\\python.exe eval\\build_relabel_review.py --apply",
            "```",
            "",
        ]
    )
    REVIEW_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REVIEW_PATH}")
    print(f"multi_or_cross={len(multi_gold)}: {multi_gold}")

    if args.apply:
        by_id = {r["id"]: r["suggested"] for r in rows}
        for case in cases:
            case["relevant_ids"] = by_id[case["id"]]
        CASES_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"applied suggestions -> {CASES_PATH}")
    else:
        print("dry-run only; pass --apply after manual review to overwrite retrieval_cases.json")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
