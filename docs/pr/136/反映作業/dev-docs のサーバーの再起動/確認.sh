#!/bin/sh
set -u

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# 読み込みの後の status が、配信元のファイルも git もたどらずに 5 秒以内に応答するか
LIMIT=5
REQUEST='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"status","arguments":{"format":"json"}}}'
response=$(curl -s -w '\n%{http_code} %{time_total}' --max-time "$LIMIT" -X POST http://127.0.0.1:8781/_admin/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$REQUEST")
result=$(printf '%s' "$response" | tail -n 1)
body=$(printf '%s' "$response" | sed '$d')
code=${result% *}
seconds=${result#* }
if [ "$code" != "200" ]; then
  echo "status の呼び出し: failed（HTTP $code。$LIMIT 秒以内に応答しない）"
  exit 1
fi
if printf '%s' "$body" | grep -q '"loading":false'; then
  echo "status の応答: ok（$seconds 秒・loading: false）"
else
  echo "status の応答: failed（loading: false を返さない）"
  exit 1
fi
