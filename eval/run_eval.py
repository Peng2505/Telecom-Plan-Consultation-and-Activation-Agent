"""对 /v1/chat 做关键字评测（需先启动 main.py）。"""
import json
import os
import sys
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


def extract_text(payload: dict) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(payload, ensure_ascii=False)


def main():
    cases_path = Path(__file__).with_name("cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    passed = 0
    rows = []
    for case in cases:
        body = {
            "user_id": "eval_user",
            "conversation_id": f"eval_{case['id']}",
            "message": case["message"],
            "stream": False,
        }
        try:
            resp = requests.post(f"{BASE}/v1/chat", headers=headers(), json=body, timeout=120)
            resp.raise_for_status()
            text = extract_text(resp.json())
        except Exception as e:
            text = f"ERROR: {e}"
        ok = any(k in text for k in case["expect_any"])
        if ok:
            for bad in case.get("forbid", []):
                if bad in text:
                    ok = False
                    break
        passed += int(ok)
        mark = "PASS" if ok else "FAIL"
        rows.append((mark, case["id"], case["message"], text[:120].replace("\n", " ")))
        print(f"[{mark}] {case['id']}: {case['message']}")
        if not ok:
            print(f"      got: {text[:200]}")

    total = len(cases)
    result = {
        "passed": passed,
        "total": total,
        "rows": [{"mark": r[0], "id": r[1], "message": r[2], "snippet": r[3]} for r in rows],
    }
    out_path = Path(__file__).with_name("last_result.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{total} passed (saved {out_path})")
    sys.exit(0 if passed >= 8 else 1)


if __name__ == "__main__":
    main()
