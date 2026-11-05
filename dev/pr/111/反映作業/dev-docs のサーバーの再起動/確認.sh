#!/bin/sh
set -u

# 稼働中のサーバーの write_docs の description に、点検できなかったキーを返す unchecked の説明が入っているか
tools=$(curl -s -X POST http://127.0.0.1:8781/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
if printf '%s' "$tools" | grep -q 'unchecked に返却する'; then
  echo "write_docs の description の unchecked: ok"
else
  echo "write_docs の description の unchecked: failed（tools/list の write_docs の description に「unchecked に返却する」が無い）"
  exit 1
fi
