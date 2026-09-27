#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://api:8012}"
echo "[web] waiting for API at ${API_BASE_URL}/health ..."
python - <<'PY'
import os, time, sys
import urllib.request

base = os.environ.get("API_BASE_URL", "http://api:8012").rstrip("/")
url = f"{base}/health"
deadline = time.time() + 120
last = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status == 200:
                print("[web] api ready")
                sys.exit(0)
    except Exception as exc:
        last = exc
        time.sleep(2)
print(f"[web] api not ready: {last}", file=sys.stderr)
sys.exit(1)
PY

echo "[web] starting Gradio"
exec python webUI.py
