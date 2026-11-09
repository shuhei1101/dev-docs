#!/bin/sh
set -u

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# 文書の MCP の tools/list で、search_docs の引数 before の説明が修正後の文言になるか
REQUEST='{"jsonrpc":"2.0","id":3,"method":"tools/list"}'
EXPECTED='該当した行の前に返却する行の数。省けば context_lines'
response=$(curl -s -w '\n%{http_code}' --max-time 60 -X POST http://127.0.0.1:8781/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$REQUEST")
code=$(printf '%s' "$response" | tail -n 1)
body=$(printf '%s' "$response" | sed '$d')
if [ "$code" != "200" ]; then
  echo "tools/list の呼び出し: failed（HTTP $code）"
  exit 1
fi
echo "tools/list の呼び出し: ok"
if printf '%s' "$body" | grep -q "$EXPECTED"; then
  echo "before の説明の文言: ok（$EXPECTED）"
else
  echo "before の説明の文言: failed（$(printf '%s' "$body" | grep -o '行の前に[^"]*' | head -n 1)）"
  exit 1
fi
