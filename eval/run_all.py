"""汇总分层评测：检索 / 忠实度 / 单轮 / 多轮，并写出对比表。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
EVAL = Path(__file__).resolve().parent
PYTHON = sys.executable


def run_script(rel: str) -> int:
    print(f"\n===== RUN {rel} =====")
    completed = subprocess.run([PYTHON, str(EVAL / rel)], cwd=str(ROOT))
    return completed.returncode


def load_json(name: str):
    path = EVAL / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Run layered evals and write summary table")
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="只跑检索评测（不需要 main.py）",
    )
    parser.add_argument(
        "--with-injection",
        action="store_true",
        help="额外跑 Prompt 注入渗透评测",
    )
    parser.add_argument(
        "--with-ragas",
        action="store_true",
        help="额外跑 RAGAS + LLM-as-Judge（较慢、耗 Token）",
    )
    parser.add_argument(
        "--label",
        default="baseline",
        help="本次结果标签，例如 baseline / after_prompt_fix",
    )
    args = parser.parse_args()

    codes = {}
    codes["retrieval"] = run_script("run_retrieval_eval.py")
    if not args.skip_api:
        codes["faithfulness"] = run_script("run_faithfulness_eval.py")
        codes["single_turn"] = run_script("run_eval.py")
        codes["conversation"] = run_script("run_conversation_eval.py")
        if args.with_injection:
            codes["injection"] = run_script("run_injection_eval.py")
        if args.with_ragas:
            codes["ragas"] = run_script("run_ragas_eval.py")

    retrieval = load_json("last_retrieval_result.json") or {}
    faith = load_json("last_faithfulness_result.json") or {}
    single = load_json("last_result.json") or {}
    multi = load_json("last_conversation_result.json") or {}
    injection = load_json("last_injection_result.json") or {}
    ragas = load_json("last_ragas_result.json") or {}

    table = [
        {
            "layer": "retrieval",
            "hit_rate_at_k": retrieval.get("hit_rate_at_k"),
            "mrr": retrieval.get("mrr"),
            "passed": f"{retrieval.get('passed', '-')}/{retrieval.get('total', '-')}",
            "exit_code": codes.get("retrieval"),
            "failed_ids": retrieval.get("failed_ids", []),
        },
        {
            "layer": "faithfulness",
            "field_hit_rate": faith.get("field_hit_rate"),
            "numeric_hallucination_rate": faith.get("numeric_hallucination_rate"),
            "passed": f"{faith.get('passed', '-')}/{faith.get('total', '-')}",
            "exit_code": codes.get("faithfulness"),
            "failed_ids": faith.get("failed_ids", []),
        },
        {
            "layer": "single_turn_e2e",
            "passed": f"{single.get('passed', '-')}/{single.get('total', '-')}",
            "exit_code": codes.get("single_turn"),
        },
        {
            "layer": "multi_turn_e2e",
            "passed": f"{multi.get('passed', '-')}/{multi.get('total', '-')}",
            "exit_code": codes.get("conversation"),
        },
    ]
    if args.with_injection:
        table.append(
            {
                "layer": "injection",
                "interception_rate": injection.get("interception_rate"),
                "passed": f"{injection.get('passed', '-')}/{injection.get('total', '-')}",
                "exit_code": codes.get("injection"),
                "failed_ids": injection.get("failed_ids", []),
            }
        )
    if args.with_ragas:
        table.append(
            {
                "layer": "ragas_llm_judge",
                "faithfulness": ragas.get("faithfulness"),
                "answer_relevancy": ragas.get("answer_relevancy"),
                "judge_pass_rate": ragas.get("judge_pass_rate"),
                "automated_hours": (ragas.get("timing") or {}).get("automated_hours"),
                "exit_code": codes.get("ragas"),
            }
        )

    summary = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table": table,
        "improvement_loop": [
            "1. 跑出 baseline（本脚本）",
            "2. 挑 1 个低分用例（检索 failed_ids 或 faithfulness failed_ids）",
            "3. 定位根因：哪一节没召回 / 哪句说了错数字",
            "4. 只改一处：分块 / Top-K / 提示词 / 工具约束",
            "5. 重跑同一用例集（换 --label）",
            "6. 对比两次 last_eval_summary_*.json 出对比表",
        ],
    }

    out = EVAL / f"last_eval_summary_{args.label}.json"
    latest = EVAL / "last_eval_summary.json"
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    print("\n===== SUMMARY =====")
    for row in table:
        print(row)
    print(f"\nsaved {out}")
    print(f"saved {latest}")

    # 检索失败或忠实度失败则整体非 0；允许 skip-api 时只看检索
    bad = [c for name, c in codes.items() if c not in (0, None)]
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
