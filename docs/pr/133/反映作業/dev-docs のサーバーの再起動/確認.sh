#!/bin/sh
set -u

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# 作業場所を指定しない search_docs のエラーの案内が、修正後の文言になるか
REQUEST='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_docs","arguments":{"source":"knowledge","view":"ids"}}}'
EXPECTED='今の作業場所から使用できる配信元を確認してください'
response=$(curl -s -w '\n%{http_code}' --max-time 60 -X POST http://127.0.0.1:8781/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$REQUEST")
code=$(printf '%s' "$response" | tail -n 1)
body=$(printf '%s' "$response" | sed '$d')
if [ "$code" != "200" ]; then
  echo "search_docs の呼び出し: failed（HTTP $code）"
  exit 1
fi
echo "search_docs の呼び出し: ok"
if printf '%s' "$body" | grep -q "$EXPECTED"; then
  echo "エラーの案内の文言: ok（$EXPECTED）"
else
  echo "エラーの案内の文言: failed（$(printf '%s' "$body" | grep -o 'describe() で[^\\]*' | head -n 1)）"
  exit 1
fi
