#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$ROOT_DIR/.env"

env_value() {
  local name="$1"
  local default="${2:-}"
  python3 - "$ENV_FILE" "$name" "$default" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
name = sys.argv[2]
default = sys.argv[3]
value = default
if path.exists():
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.strip() == name:
            value = val.strip().strip('"').strip("'")
print(value)
PY
}

post_onebot() {
  local path="$1"
  local url="${ONEBOT_HTTP_URL%/}${path}"
  if [ -n "$ONEBOT_ACCESS_TOKEN" ]; then
    curl -sS -m 8 -X POST "$url" \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $ONEBOT_ACCESS_TOKEN" \
      -d '{}'
  else
    curl -sS -m 8 -X POST "$url" \
      -H 'Content-Type: application/json' \
      -d '{}'
  fi
}

summarize_login() {
  python3 -c '
import json
import sys

raw = sys.stdin.read()
try:
    payload = json.loads(raw)
except Exception:
    print(raw.strip() or "(empty response)")
    raise SystemExit(0)

data = payload.get("data") or {}
print(
    "status={status} retcode={retcode} user_id={user_id} nickname={nickname}".format(
        status=payload.get("status"),
        retcode=payload.get("retcode"),
        user_id=data.get("user_id"),
        nickname=data.get("nickname"),
    )
)
'
}

summarize_groups() {
  local groups_csv="$1"
  python3 -c '
import json
import sys

want = {int(item.strip()) for item in sys.argv[1].replace(";", ",").split(",") if item.strip().isdigit()}
raw = sys.stdin.read()
try:
    payload = json.loads(raw)
except Exception:
    print(raw.strip() or "(empty response)")
    raise SystemExit(0)

groups = payload.get("data") or []
found = {int(item.get("group_id")): item for item in groups if str(item.get("group_id", "")).isdigit()}
if not want:
    print(f"group_count={len(groups)}")
    raise SystemExit(0)

for group_id in sorted(want):
    item = found.get(group_id)
    if item:
        name = item.get("group_name", "")
        members = item.get("member_count")
        print(f"FOUND {group_id} {name} members={members}")
    else:
        print(f"MISSING {group_id}")
' "$groups_csv"
}

BOT_PORT="$(env_value BOT_PORT 8088)"
BOT_ALLOWED_GROUPS="$(env_value BOT_ALLOWED_GROUPS "")"
ONEBOT_HTTP_URL="$(env_value ONEBOT_HTTP_URL http://127.0.0.1:3000)"
ONEBOT_ACCESS_TOKEN="$(env_value ONEBOT_ACCESS_TOKEN "")"
GROUPS_TO_CHECK="${1:-$BOT_ALLOWED_GROUPS}"

cd "$ROOT_DIR"

echo "=== bot health ==="
curl -sS -m 5 "http://127.0.0.1:${BOT_PORT}/health" || true
echo

echo "=== onebot api ==="
echo "url=${ONEBOT_HTTP_URL%/}"
if [ -n "$ONEBOT_ACCESS_TOKEN" ]; then
  echo "token_set=true"
else
  echo "token_set=false"
fi

echo "=== onebot login ==="
if login_json="$(post_onebot /get_login_info 2>&1)"; then
  printf '%s' "$login_json" | summarize_login
else
  echo "$login_json"
fi

echo "=== onebot groups ==="
if group_json="$(post_onebot /get_group_list 2>&1)"; then
  printf '%s' "$group_json" | summarize_groups "$GROUPS_TO_CHECK"
else
  echo "$group_json"
fi

echo "=== recent bot logs ==="
docker compose logs --since=20m qq-cf-bot 2>/dev/null \
  | grep -E 'onebot post received|onebot event rejected|onebot command ingress|bot command accepted|bot command blocked|failed to handle command|listening' \
  || true

echo "=== recent napcat logs, if local service exists ==="
if docker compose ps napcat >/dev/null 2>&1; then
  docker compose logs --since=20m napcat 2>/dev/null \
    | grep -E '账号状态|KickedOffline|Login|二维码|HTTP服务|HTTP上报|接收 <- 群聊|发送 -> 群聊' \
    || true
else
  echo "no local napcat service in this compose project"
fi
