"""多轮画像、确认与工单幂等回归测试（需先启动 main.py）。

支持两种用例格式：
1) 旧版扁平 turns 列表（兼容）
2) 多脚本：[{id, turns: [...]}, ...]
"""
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


def _headers():
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


def _extract_text(payload: dict) -> str:
    return payload["choices"][0]["message"]["content"]


def _normalize_scripts(raw):
    if not raw:
        return []
    if isinstance(raw[0], dict) and "turns" in raw[0]:
        return raw
    return [{"id": "default", "turns": raw}]


def _eval_turn(text: str, case: dict) -> dict:
    expect_all = case.get("expect_all", [])
    expect_any = case.get("expect_any", [])
    forbidden = case.get("forbid", [])
    missing_all = [word for word in expect_all if word not in text]
    any_ok = not expect_any or any(word in text for word in expect_any)
    present_forbidden = [word for word in forbidden if word in text]
    ok = not missing_all and any_ok and not present_forbidden
    return {
        "ok": ok,
        "missing_all": missing_all,
        "expect_any_ok": any_ok,
        "forbidden_found": present_forbidden,
        "response": text,
    }


def main():
    raw = json.loads(
        Path(__file__).with_name("conversation_cases.json").read_text(encoding="utf-8")
    )
    scripts = _normalize_scripts(raw)
    all_rows = []
    script_summaries = []

    for script in scripts:
        script_id = script.get("id", "unnamed")
        suffix = uuid.uuid4().hex[:8]
        user_id = f"conversation_eval_{script_id}_{suffix}"
        conversation_id = f"{script_id}_{suffix}"
        rows = []
        print(f"\n===== SCRIPT {script_id} =====")
        for index, case in enumerate(script["turns"], start=1):
            response = requests.post(
                f"{BASE}/v1/chat",
                headers=_headers(),
                json={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message": case["message"],
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            text = _extract_text(response.json())
            detail = _eval_turn(text, case)
            row = {
                "script": script_id,
                "turn": index,
                "message": case["message"],
                **detail,
            }
            rows.append(row)
            all_rows.append(row)
            print(f"[{'PASS' if detail['ok'] else 'FAIL'}] turn {index}: {case['message']}")
            if not detail["ok"]:
                print(
                    f"  missing={detail['missing_all']}, any_ok={detail['expect_any_ok']}, "
                    f"forbidden={detail['forbidden_found']}"
                )
                print(f"  response={text[:500]}")

        passed = sum(int(r["ok"]) for r in rows)
        script_summaries.append(
            {
                "id": script_id,
                "passed": passed,
                "total": len(rows),
                "user_id": user_id,
            }
        )

    passed = sum(int(row["ok"]) for row in all_rows)
    result = {
        "passed": passed,
        "total": len(all_rows),
        "scripts": script_summaries,
        "rows": all_rows,
    }
    output = Path(__file__).with_name("last_conversation_result.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(all_rows)} turns passed (saved {output})")
    sys.exit(0 if passed == len(all_rows) else 1)


if __name__ == "__main__":
    main()
