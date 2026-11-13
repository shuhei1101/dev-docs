#!/bin/sh
set -u

# 画面の API で dev-docs の配信元の文書が 200 で返るか
code=$(curl -s -m 45 -o /dev/null -w '%{http_code}' http://127.0.0.1:8781/_api/sources/dev-docs/docs || true)
if [ "$code" = "200" ]; then
  echo "画面の API の文書の取得: ok（HTTP 200）"
else
  echo "画面の API の文書の取得: failed（HTTP $code）"
  exit 1
fi

# 管理の MCP の status が project-index につながっている旨を返すか
STATUS='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"status","arguments":{}}}'
body=$(curl -s -m 60 -X POST http://127.0.0.1:8781/_admin/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$STATUS")
line=$(printf '%s' "$body" | grep -o 'project-index: [^\\"]*' | head -n 1)
case "$line" in
  *つながっている*) echo "管理の MCP の status: ok（$line）" ;;
  *) echo "管理の MCP の status: failed（${line:-project-index の行が無い}）"; exit 1 ;;
esac
