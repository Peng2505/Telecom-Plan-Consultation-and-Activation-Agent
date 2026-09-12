"""检索层评测：Hit Rate@K 与 MRR（只测 Chroma，不调对话大模型）。"""
from __future__ import annotations

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

from utils.config import Config
from utils.llms import get_llm

K = int(os.getenv("RETRIEVAL_TOP_K", "3"))


def hit_at_k(ranked_ids: list, relevant: set, k: int) -> float:
    return 1.0 if any(i in relevant for i in ranked_ids[:k]) else 0.0


def mrr(ranked_ids: list, relevant: set) -> float:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / index
    return 0.0


def main():
    cases = json.loads(Path(__file__).with_name("retrieval_cases.json").read_text(encoding="utf-8"))
    _, embeddings = get_llm(Config.LLM_TYPE)
    client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
    try:
        collection = client.get_collection(Config.CHROMADB_COLLECTION_NAME)
    except Exception as exc:
        print(f"ERROR: 找不到集合 {Config.CHROMADB_COLLECTION_NAME}，请先运行 vectorSaveTest.py\n{exc}")
        sys.exit(1)

    rows = []
    hits = []
    mrrs = []
    for case in cases:
        query = case["query"]
        relevant = set(case["relevant_ids"])
        query_emb = embeddings.embed_query(query)
        result = collection.query(query_embeddings=[query_emb], n_results=K)
        ranked_ids = (result.get("ids") or [[]])[0]
        hit = hit_at_k(ranked_ids, relevant, K)
        score = mrr(ranked_ids, relevant)
        hits.append(hit)
        mrrs.append(score)
        ok = hit >= 1.0
        rows.append(
            {
                "id": case["id"],
                "query": query,
                "relevant_ids": case["relevant_ids"],
                "retrieved_ids": ranked_ids,
                "hit_at_k": hit,
                "mrr": round(score, 4),
                "ok": ok,
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {case['id']}: hit={hit:.0f} mrr={score:.3f} got={ranked_ids}")

    total = len(cases)
    hit_rate = sum(hits) / total if total else 0.0
    mean_mrr = sum(mrrs) / total if total else 0.0
    failed = [r for r in rows if not r["ok"]]
    summary = {
        "metric": "retrieval",
        "top_k": K,
        "total": total,
        "hit_rate_at_k": round(hit_rate, 4),
        "mrr": round(mean_mrr, 4),
        "passed": total - len(failed),
        "failed_ids": [r["id"] for r in failed],
        "rows": rows,
        "note": "小样本知识库，Hit Rate 可能偏高；用于定位未召回的低分用例。",
    }
    out = Path(__file__).with_name("last_retrieval_result.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nHit@{K}={hit_rate:.3f}  MRR={mean_mrr:.3f}  ({summary['passed']}/{total})")
    print(f"saved {out}")
    # 允许个别 miss，但过低则失败
    sys.exit(0 if hit_rate >= 0.7 else 1)


if __name__ == "__main__":
    main()
