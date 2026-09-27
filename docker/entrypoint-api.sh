#!/usr/bin/env bash
set -euo pipefail

echo "[api] waiting for postgres..."
python - <<'PY'
import os, time, sys
import psycopg

uri = os.environ.get(
    "DB_URI",
    "postgresql://postgres:postgres@postgres:5432/postgres?sslmode=disable",
)
# psycopg3 prefers postgresql:// ; strip query if needed for connect
deadline = time.time() + 90
last = None
while time.time() < deadline:
    try:
        with psycopg.connect(uri, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("[api] postgres ready")
        sys.exit(0)
    except Exception as exc:
        last = exc
        time.sleep(2)
print(f"[api] postgres not ready: {last}", file=sys.stderr)
sys.exit(1)
PY

RUN_INGEST="${RUN_INGEST:-auto}"
if [ "$RUN_INGEST" = "1" ] || [ "$RUN_INGEST" = "true" ]; then
  echo "[api] RUN_INGEST forced, ingesting knowledge..."
  python vectorSaveTest.py
elif [ "$RUN_INGEST" = "auto" ]; then
  python - <<'PY'
import os, sys
import chromadb
from utils.config import Config

path = Config.CHROMADB_DIRECTORY
name = Config.CHROMADB_COLLECTION_NAME
try:
    client = chromadb.PersistentClient(path=path)
    names = []
    for c in client.list_collections():
        names.append(c if isinstance(c, str) else getattr(c, "name", str(c)))
    if name in names:
        coll = client.get_collection(name)
        n = coll.count()
        print(f"[api] chroma collection {name} exists count={n}, skip ingest")
        sys.exit(0)
except Exception as exc:
    print(f"[api] chroma check failed ({exc}), will ingest")
sys.exit(2)
PY
  status=$?
  if [ "$status" -eq 2 ]; then
    echo "[api] ingesting knowledge into Chroma..."
    python vectorSaveTest.py
  fi
fi

echo "[api] starting FastAPI on ${HOST:-0.0.0.0}:${PORT:-8012}"
exec python main.py
