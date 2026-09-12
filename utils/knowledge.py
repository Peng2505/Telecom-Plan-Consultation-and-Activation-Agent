"""套餐知识库切分与稳定 chunk id（入库与检索评测共用）。"""
from __future__ import annotations

import re
from typing import List, Tuple

# 标题 -> 稳定 id（评测标注依赖这些 id，勿随意改名）
HEADING_TO_ID = {
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


def load_knowledge_chunks(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return split_markdown_sections(text)
