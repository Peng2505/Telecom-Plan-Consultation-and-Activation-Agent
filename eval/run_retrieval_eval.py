"""检索层评测：Hit Rate@K 与 MRR。

默认只测原始 query → Chroma。
加 --with-rewrite 时先走与线上一致的 Query Rewrite 提示词，再检索（用于第三张对比表）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import chromadb
from langchain_core.prompts import PromptTemplate

from utils.config import Config
from utils.llms import get_llm

K = Config.RETRIEVAL_TOP_K
COLLECTION = os.getenv(
    "EVAL_CHROMA_COLLECTION",
    os.getenv("CHROMADB_COLLECTION_V2", Config.CHROMADB_COLLECTION_NAME),
)


def hit_at_k(ranked_ids: list, relevant: set, k: int) -> float:
    return 1.0 if any(i in relevant for i in ranked_ids[:k]) else 0.0


def mrr(ranked_ids: list, relevant: set) -> float:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / index
    return 0.0


def load_rewrite_chain(llm_chat):
    path = Config.PROMPT_TEMPLATE_TXT_REWRITE
    text = Path(path).read_text(encoding="utf-8")
    prompt = PromptTemplate.from_template(text)
    return prompt | llm_chat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-rewrite",
        action="store_true",
        help="先用 prompt_template_rewrite.txt 改写 query 再检索",
    )
    parser.add_argument(
        "--cases",
        default="",
        help="用例 JSON（默认 retrieval_cases.json；可用 retrieval_cases_dev/holdout.json）",
    )
    parser.add_argument(
        "--out",
        default="",
        help="结果 JSON 路径（默认 last_retrieval_result.json）",
    )
    parser.add_argument(
        "--label",
        default="",
        help="写入结果 JSON 的 split/label 字段",
    )
    args = parser.parse_args()

    cases_path = Path(__file__).with_name(args.cases) if args.cases else Path(__file__).with_name("retrieval_cases.json")
    if not cases_path.exists():
        # allow relative path from eval/ or repo root
        alt = Path(args.cases)
        cases_path = alt if alt.exists() else Path(__file__).parent / args.cases
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    llm_chat, embeddings = get_llm(Config.LLM_TYPE)
    rewrite_chain = load_rewrite_chain(llm_chat) if args.with_rewrite else None

    client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
    try:
        collection = client.get_collection(COLLECTION)
    except Exception as exc:
        print(f"ERROR: 找不到集合 {COLLECTION}，请先运行 vectorSaveTest.py 写入 policy_v2\n{exc}")
        sys.exit(1)
    print(
        f"collection={COLLECTION} top_k={K} cases={len(cases)} "
        f"file={cases_path.name} with_rewrite={args.with_rewrite}"
    )

    rows = []
    hits = []
    mrrs = []
    for case in cases:
        query = case["query"]
        rewritten = None
        search_query = query
        if rewrite_chain is not None:
            resp = rewrite_chain.invoke({"question": query})
            rewritten = getattr(resp, "content", str(resp)).strip()
            # 回退：空结果或明显失败时用原文
            if not rewritten or rewritten.startswith("无法") or rewritten.startswith("评分"):
                rewritten = query
            search_query = rewritten
        relevant = set(case["relevant_ids"])
        query_emb = embeddings.embed_query(search_query)
        result = collection.query(query_embeddings=[query_emb], n_results=K)
        ranked_ids = (result.get("ids") or [[]])[0]
        hit = hit_at_k(ranked_ids, relevant, K)
        score = mrr(ranked_ids, relevant)
        hits.append(hit)
        mrrs.append(score)
        ok = hit >= 1.0
        row = {
            "id": case["id"],
            "query": query,
            "search_query": search_query,
            "relevant_ids": case["relevant_ids"],
            "retrieved_ids": ranked_ids,
            "hit_at_k": hit,
            "mrr": round(score, 4),
            "ok": ok,
        }
        if rewritten is not None:
            row["rewritten"] = rewritten
        rows.append(row)
        extra = f" | rw={rewritten[:48]}" if rewritten and rewritten != query else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {case['id']}: hit={hit:.0f} mrr={score:.3f} got={ranked_ids}{extra}")

    total = len(cases)
    hit_rate = sum(hits) / total if total else 0.0
    mean_mrr = sum(mrrs) / total if total else 0.0
    failed = [r for r in rows if not r["ok"]]
    summary = {
        "metric": "retrieval",
        "label": args.label or ("holdout" if "holdout" in cases_path.name else "default"),
        "cases_file": str(cases_path.name),
        "collection": COLLECTION,
        "top_k": K,
        "with_rewrite": args.with_rewrite,
        "total": total,
        "hit_rate_at_k": round(hit_rate, 4),
        "mrr": round(mean_mrr, 4),
        "passed": total - len(failed),
        "failed_ids": [r["id"] for r in failed],
        "rows": rows,
        "note": "holdout 仅用于报告；dev 用于定位/回归。勿在 holdout 上继续调参。",
    }
    out = Path(__file__).with_name(args.out or "last_retrieval_result.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nHit@{K}={hit_rate:.3f}  MRR={mean_mrr:.3f}  ({summary['passed']}/{total})")
    print(f"saved {out}")
    sys.exit(0 if hit_rate >= 0.5 else 1)


if __name__ == "__main__":
    main()
