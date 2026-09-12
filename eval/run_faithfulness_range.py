"""忠实度评测连跑多次，输出通过率区间（应对 LLM 波动）。"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parent
PYTHON = sys.executable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    results = []
    for i in range(1, runs + 1):
        print(f"\n===== FAITHFULNESS RUN {i}/{runs} =====")
        code = subprocess.run([PYTHON, str(EVAL / "run_faithfulness_eval.py")], cwd=str(ROOT)).returncode
        data = json.loads((EVAL / "last_faithfulness_result.json").read_text(encoding="utf-8"))
        snap = EVAL / f"last_faithfulness_run_{i}.json"
        snap.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(
            {
                "run": i,
                "exit_code": code,
                "passed": f"{data['passed']}/{data['total']}",
                "field_hit_rate": data["field_hit_rate"],
                "numeric_hallucination_rate": data["numeric_hallucination_rate"],
                "failed_ids": data.get("failed_ids", []),
            }
        )
        print(
            f"run={i} field_hit={data['field_hit_rate']} halluc={data['numeric_hallucination_rate']} "
            f"passed={data['passed']}/{data['total']} failed={data.get('failed_ids')}"
        )

    field_vals = [r["field_hit_rate"] for r in results]
    pass_vals = [int(r["passed"].split("/")[0]) for r in results]
    total_cases = int(results[0]["passed"].split("/")[1])
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runs": results,
        "field_hit_rate_range": [min(field_vals), max(field_vals)],
        "passed_count_range": [min(pass_vals), max(pass_vals)],
        "total_cases": total_cases,
        "note": "区间用于说明 LLM 波动；简历优先写区间而非单次满分。",
    }
    out = EVAL / "last_faithfulness_range.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfield_hit_rate_range={summary['field_hit_rate_range']}")
    print(f"passed_count_range={summary['passed_count_range']}/{summary['total_cases']}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
