"""工具忠实度 / 数字幻觉率评测（走 /v1/chat，检查 must_include 与 forbid）。"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

BASE = os.getenv("EVAL_BASE_URL", "http://127.0.0.1:8012")
API_KEY = os.getenv("APP_API_KEY", "").strip()


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


def score_case(text: str, case: dict) -> dict:
    must = case.get("must_include", [])
    must_any = case.get("must_include_any", [])
    forbid = case.get("forbid", [])

    must_hits = [k for k in must if k in text]
    must_miss = [k for k in must if k not in text]
    any_ok = (not must_any) or any(k in text for k in must_any)
    forbidden_hits = [k for k in forbid if k in text]

    field_total = len(must)
    field_hit_rate = (len(must_hits) / field_total) if field_total else (1.0 if any_ok else 0.0)
    hallucinated = bool(forbidden_hits)
    ok = (not must_miss) and any_ok and (not forbidden_hits)
    return {
        "ok": ok,
        "field_hit_rate": round(field_hit_rate, 4),
        "must_hits": must_hits,
        "must_miss": must_miss,
        "any_ok": any_ok,
        "forbidden_hits": forbidden_hits,
        "hallucinated": hallucinated,
    }


def main():
    cases = json.loads(Path(__file__).with_name("faithfulness_cases.json").read_text(encoding="utf-8"))
    rows = []
    field_rates = []
    halluc_flags = []

    for case in cases:
        suffix = uuid.uuid4().hex[:8]
        user_id = f"faith_{suffix}"
        conversation_id = f"faith_conv_{case['id']}_{suffix}"
        last_text = ""
        try:
            for message in case["messages"]:
                last_text = chat(user_id, conversation_id, message)
            metrics = score_case(last_text, case)
        except Exception as exc:
            last_text = f"ERROR: {exc}"
            metrics = {
                "ok": False,
                "field_hit_rate": 0.0,
                "must_hits": [],
                "must_miss": case.get("must_include", []),
                "any_ok": False,
                "forbidden_hits": [],
                "hallucinated": False,
                "error": str(exc),
            }

        field_rates.append(metrics["field_hit_rate"])
        halluc_flags.append(1.0 if metrics.get("hallucinated") else 0.0)
        rows.append(
            {
                "id": case["id"],
                "messages": case["messages"],
                "response": last_text,
                **metrics,
            }
        )
        print(
            f"[{'PASS' if metrics['ok'] else 'FAIL'}] {case['id']}: "
            f"field_hit={metrics['field_hit_rate']:.2f} halluc={metrics.get('hallucinated')}"
        )
        if not metrics["ok"]:
            print(f"      miss={metrics.get('must_miss')} forbid={metrics.get('forbidden_hits')}")
            print(f"      text={last_text[:220].replace(chr(10), ' ')}")

    total = len(cases)
    mean_field = sum(field_rates) / total if total else 0.0
    halluc_rate = sum(halluc_flags) / total if total else 0.0
    passed = sum(1 for r in rows if r["ok"])
    summary = {
        "metric": "faithfulness",
        "total": total,
        "passed": passed,
        "field_hit_rate": round(mean_field, 4),
        "numeric_hallucination_rate": round(halluc_rate, 4),
        "failed_ids": [r["id"] for r in rows if not r["ok"]],
        "rows": rows,
        "definition": {
            "field_hit_rate": "must_include 命中数 / must_include 总数（按用例平均）",
            "numeric_hallucination_rate": "出现 forbid 错误数字或虚假开通话术的用例比例",
        },
    }
    out = Path(__file__).with_name("last_faithfulness_result.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nfield_hit_rate={mean_field:.3f}  numeric_hallucination_rate={halluc_rate:.3f}  "
        f"({passed}/{total})"
    )
    print(f"saved {out}")
    sys.exit(0 if passed >= max(1, total - 2) and halluc_rate <= 0.25 else 1)


if __name__ == "__main__":
    main()
