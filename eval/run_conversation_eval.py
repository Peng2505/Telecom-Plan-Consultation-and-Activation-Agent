"""多轮画像、确认与工单幂等回归测试（需先启动 main.py）。"""
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


def main():
    cases = json.loads(
        Path(__file__).with_name("conversation_cases.json").read_text(encoding="utf-8")
    )
    suffix = uuid.uuid4().hex[:8]
    user_id = f"conversation_eval_{suffix}"
    conversation_id = f"profile_order_{suffix}"
    rows = []

    for index, case in enumerate(cases, start=1):
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
        expect_all = case.get("expect_all", [])
        expect_any = case.get("expect_any", [])
        forbidden = case.get("forbid", [])
        missing_all = [word for word in expect_all if word not in text]
        any_ok = not expect_any or any(word in text for word in expect_any)
        present_forbidden = [word for word in forbidden if word in text]
        ok = not missing_all and any_ok and not present_forbidden
        rows.append(
            {
                "turn": index,
                "message": case["message"],
                "ok": ok,
                "missing_all": missing_all,
                "expect_any_ok": any_ok,
                "forbidden_found": present_forbidden,
                "response": text,
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] turn {index}: {case['message']}")
        if not ok:
            print(f"  missing={missing_all}, any_ok={any_ok}, forbidden={present_forbidden}")
            print(f"  response={text[:500]}")

    passed = sum(int(row["ok"]) for row in rows)
    result = {"passed": passed, "total": len(rows), "user_id": user_id, "rows": rows}
    output = Path(__file__).with_name("last_conversation_result.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(rows)} turns passed (saved {output})")
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
