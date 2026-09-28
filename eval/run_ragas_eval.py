"""RAGAS 对齐指标（Faithfulness / Answer Relevancy）+ LLM-as-Judge + 回归耗时。

优先调用 ragas 库；若环境不兼容则使用同定义的 LLM 评分回退实现，保证可复现出数。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import requests
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

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

from utils.config import Config
from utils.plans import dumps, estimate_overage_data, lookup_plan_data, overage_meta, recommend_plan_data

BASE = os.getenv("EVAL_BASE_URL", "http://127.0.0.1:8012")
API_KEY = os.getenv("APP_API_KEY", "").strip()
MANUAL_MINUTES_PER_CASE = float(os.getenv("EVAL_MANUAL_MINUTES_PER_CASE", "4"))


def headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def chat(user_id: str, conversation_id: str, message: str) -> str:
    resp = requests.post(
        f"{BASE}/v1/chat",
        headers=headers(),
        json={
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message": message,
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        model=os.getenv("QWEN_CHAT_MODEL", "qwen-plus"),
        temperature=0.0,
        timeout=60,
        max_retries=2,
    )


def make_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v2"),
        check_embedding_ctx_length=False,
    )


def build_contexts(case: dict, embeddings: OpenAIEmbeddings) -> list[str]:
    mode = case.get("context_mode", "retrieve")
    if mode == "tool_lookup":
        return [dumps(lookup_plan_data(case.get("lookup_query", ""), campus_student=False))]
    if mode == "tool_recommend":
        return [
            dumps(
                recommend_plan_data(
                    float(case.get("monthly_usage_gb", 50)),
                    bool(case.get("campus_student", False)),
                )
            )
        ]
    if mode == "tool_estimate":
        return [
            dumps(
                estimate_overage_data(
                    float(case.get("monthly_usage_gb", 25)),
                    case.get("current_plan", "经济套餐"),
                )
            )
        ]
    if mode == "tool_overage_meta":
        ctx = [dumps(overage_meta())]
        q = case.get("retrieve_query")
        if q:
            ctx.extend(_retrieve_chunks(q, embeddings))
        return ctx
    return _retrieve_chunks(case.get("retrieve_query") or case["messages"][-1], embeddings)


def _retrieve_chunks(query: str, embeddings: OpenAIEmbeddings) -> list[str]:
    client = chromadb.PersistentClient(path=Config.CHROMADB_DIRECTORY)
    collection = client.get_collection(Config.CHROMADB_COLLECTION_NAME)
    emb = embeddings.embed_query(query)
    result = collection.query(query_embeddings=[emb], n_results=Config.RETRIEVAL_TOP_K)
    docs = (result.get("documents") or [[]])[0]
    return [d for d in docs if d]


def _parse_json_blob(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def score_faithfulness_llm(llm: ChatOpenAI, question: str, answer: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)[:6000]
    prompt = f"""你是 RAG 忠实度评分器（对齐 RAGAS Faithfulness）。
根据「上下文」判断「答案」中的陈述是否都可由上下文支持。
只输出 JSON：{{"score": 0.0到1.0的小数, "reason": "一句中文"}}

问题：{question}
上下文：
{ctx}

答案：
{answer}
"""
    raw = llm.invoke(prompt).content
    data = _parse_json_blob(str(raw))
    try:
        return max(0.0, min(1.0, float(data.get("score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


def score_relevancy_llm(llm: ChatOpenAI, question: str, answer: str) -> float:
    prompt = f"""你是答案相关性评分器（对齐 RAGAS Answer Relevancy）。
判断答案是否紧扣用户问题、信息有用且无明显跑题。
只输出 JSON：{{"score": 0.0到1.0的小数, "reason": "一句中文"}}

问题：{question}
答案：{answer}
"""
    raw = llm.invoke(prompt).content
    data = _parse_json_blob(str(raw))
    try:
        return max(0.0, min(1.0, float(data.get("score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


def llm_judge(llm: ChatOpenAI, question: str, answer: str, contexts: list[str]) -> dict:
    ctx = "\n---\n".join(contexts)[:4000]
    prompt = f"""你是流量套餐客服质量裁判（LLM-as-Judge）。
按业务安全与正确性打分。禁止把假开通、错价判为通过。
只输出 JSON：
{{"score_1_to_5": 1到5整数, "pass": true/false, "policy_safe": true/false, "reasons": "简短中文"}}

判定要点：
- policy_safe=false：出现办理成功/已经开通/自造单价如0.29 等
- pass=true：score>=4 且 policy_safe=true，且大体回答了问题

问题：{question}
参考上下文：{ctx}
答案：{answer}
"""
    raw = llm.invoke(prompt).content
    data = _parse_json_blob(str(raw))
    score = int(data.get("score_1_to_5") or 0)
    policy_safe = bool(data.get("policy_safe", False))
    passed = bool(data.get("pass", False)) and policy_safe and score >= 4
    # 硬禁词兜底
    forbid = ("办理成功", "已经开通", "0.29", "确认办理成功", "已经扣费")
    if any(x in (answer or "") for x in forbid):
        policy_safe = False
        passed = False
    return {
        "score_1_to_5": score,
        "pass": passed,
        "policy_safe": policy_safe,
        "reasons": data.get("reasons", ""),
    }


def try_ragas_library(rows: list[dict], llm: ChatOpenAI, embeddings: OpenAIEmbeddings) -> dict | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
    except Exception as exc:
        print(f"[ragas] library unavailable, using LLM-aligned fallback: {exc}")
        return None

    dataset = Dataset.from_dict(
        {
            "question": [r["question"] for r in rows],
            "answer": [r["answer"] for r in rows],
            "contexts": [r["contexts"] for r in rows],
        }
    )
    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=LangchainLLMWrapper(llm),
            embeddings=LangchainEmbeddingsWrapper(embeddings),
        )
        data = result.to_pandas() if hasattr(result, "to_pandas") else None
        if data is None:
            # older dict-like
            return {
                "backend": "ragas_library",
                "faithfulness": float(result.get("faithfulness", 0) or 0),
                "answer_relevancy": float(result.get("answer_relevancy", 0) or 0),
                "per_case": [],
            }
        faith_col = "faithfulness" if "faithfulness" in data.columns else data.columns[-2]
        rel_col = "answer_relevancy" if "answer_relevancy" in data.columns else data.columns[-1]
        per = []
        for i, row in enumerate(rows):
            per.append(
                {
                    "id": row["id"],
                    "faithfulness": float(data.iloc[i][faith_col]),
                    "answer_relevancy": float(data.iloc[i][rel_col]),
                }
            )
        return {
            "backend": "ragas_library",
            "faithfulness": float(data[faith_col].mean()),
            "answer_relevancy": float(data[rel_col].mean()),
            "per_case": per,
        }
    except Exception as exc:
        print(f"[ragas] evaluate failed, fallback: {exc}")
        return None


def main():
    t0 = time.perf_counter()
    cases = json.loads(Path(__file__).with_name("ragas_cases.json").read_text(encoding="utf-8"))
    llm = make_llm()
    embeddings = make_embeddings()

    rows = []
    for case in cases:
        suffix = uuid.uuid4().hex[:8]
        user_id = f"ragas_{suffix}"
        conversation_id = f"ragas_{case['id']}_{suffix}"
        answer = ""
        for message in case["messages"]:
            answer = chat(user_id, conversation_id, message)
        question = case["messages"][-1]
        contexts = build_contexts(case, embeddings)
        rows.append(
            {
                "id": case["id"],
                "question": question,
                "messages": case["messages"],
                "answer": answer,
                "contexts": contexts,
            }
        )
        print(f"[collect] {case['id']}: contexts={len(contexts)} answer={answer[:60].replace(chr(10), ' ')}")

    ragas_part = try_ragas_library(rows, llm, embeddings)
    backend = "llm_aligned_fallback"
    per_metrics = []
    if ragas_part:
        backend = ragas_part["backend"]
        faith_mean = ragas_part["faithfulness"]
        rel_mean = ragas_part["answer_relevancy"]
        by_id = {p["id"]: p for p in ragas_part.get("per_case", [])}
        for row in rows:
            m = by_id.get(row["id"], {})
            per_metrics.append(
                {
                    "id": row["id"],
                    "faithfulness": m.get("faithfulness"),
                    "answer_relevancy": m.get("answer_relevancy"),
                }
            )
    else:
        faith_scores = []
        rel_scores = []
        for row in rows:
            f = score_faithfulness_llm(llm, row["question"], row["answer"], row["contexts"])
            r = score_relevancy_llm(llm, row["question"], row["answer"])
            faith_scores.append(f)
            rel_scores.append(r)
            per_metrics.append({"id": row["id"], "faithfulness": f, "answer_relevancy": r})
            print(f"[metric] {row['id']}: faith={f:.3f} rel={r:.3f}")
        faith_mean = sum(faith_scores) / len(faith_scores) if faith_scores else 0.0
        rel_mean = sum(rel_scores) / len(rel_scores) if rel_scores else 0.0

    judge_rows = []
    for row in rows:
        j = llm_judge(llm, row["question"], row["answer"], row["contexts"])
        judge_rows.append({"id": row["id"], **j})
        print(f"[judge] {row['id']}: pass={j['pass']} score={j['score_1_to_5']} safe={j['policy_safe']}")

    judge_pass_rate = sum(1 for j in judge_rows if j["pass"]) / len(judge_rows) if judge_rows else 0.0
    elapsed = time.perf_counter() - t0
    automated_hours = round(elapsed / 3600.0, 4)
    manual_hours = round(len(cases) * MANUAL_MINUTES_PER_CASE / 60.0, 4)

    timing = {
        "n_cases": len(cases),
        "manual_minutes_per_case": MANUAL_MINUTES_PER_CASE,
        "manual_estimate_hours": manual_hours,
        "automated_seconds": round(elapsed, 2),
        "automated_hours": automated_hours,
        "speedup_note": f"手工逐条核对估算 {manual_hours}h → 自动 RAGAS对齐+Judge {automated_hours}h",
    }

    # merge metrics into detail rows
    detail = []
    metric_by_id = {m["id"]: m for m in per_metrics}
    judge_by_id = {j["id"]: j for j in judge_rows}
    for row in rows:
        detail.append(
            {
                **row,
                **metric_by_id.get(row["id"], {}),
                "judge": judge_by_id.get(row["id"], {}),
            }
        )

    summary = {
        "metric": "ragas_llm_judge",
        "backend": backend,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total": len(cases),
        "faithfulness": round(faith_mean, 4),
        "answer_relevancy": round(rel_mean, 4),
        "judge_pass_rate": round(judge_pass_rate, 4),
        "timing": timing,
        "rows": detail,
        "definition": {
            "faithfulness": "答案陈述相对给定上下文的可支持程度（RAGAS Faithfulness 对齐）",
            "answer_relevancy": "答案与问题的相关程度（RAGAS Answer Relevancy 对齐）",
            "judge_pass_rate": "LLM-as-Judge：score>=4 且 policy_safe",
            "manual_estimate_hours": "N × 每条人工核对分钟 / 60（默认每条4分钟）",
        },
    }
    out = Path(__file__).with_name("last_ragas_result.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    timing_out = Path(__file__).with_name("last_eval_timing.json")
    timing_out.write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nbackend={backend} faithfulness={faith_mean:.3f} "
        f"answer_relevancy={rel_mean:.3f} judge_pass_rate={judge_pass_rate:.3f}"
    )
    print(timing["speedup_note"])
    print(f"saved {out}")
    print(f"saved {timing_out}")
    # 产出成功即 0；阈值用于 CI 告警，Judge 波动较大故放宽
    sys.exit(0 if faith_mean >= 0.5 and rel_mean >= 0.5 else 1)


if __name__ == "__main__":
    main()
