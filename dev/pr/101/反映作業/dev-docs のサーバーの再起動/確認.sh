#!/bin/sh
set -u

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# documents[].schema でほかの配信元のスキーマをリビジョンで指した設定を、check_project が違反なしで検査するか
# 修正の前のサーバーは `documents[0].schema` を `型が違う（期待: string）` の違反にする
FOLDER=$(mktemp -d)
trap 'rm -rf "$FOLDER"' EXIT
CONFIG='name: pr101-check
documents:
  - id: rule
    paths: [docs/*.yaml]
    schema:
      source: knowledge
      path: schemas/rule.schema.yaml
      ref: v0.4.0
'
REQUEST=$(python3 -c 'import json, sys; print(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "check_project", "arguments": {"path": sys.argv[1], "config": sys.argv[2], "format": "json"}}}))' "$FOLDER" "$CONFIG")
response=$(curl -s -w '\n%{http_code}' --max-time 60 -X POST http://127.0.0.1:8781/_admin/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$REQUEST")
code=$(printf '%s' "$response" | tail -n 1)
body=$(printf '%s' "$response" | sed '$d')
if [ "$code" != "200" ]; then
  echo "check_project の呼び出し: failed（HTTP $code）"
  exit 1
fi
echo "check_project の呼び出し: ok"
violations=$(printf '%s' "$body" | python3 -c 'import json, sys; print(json.dumps(json.load(sys.stdin)["result"]["structuredContent"].get("violations", []), ensure_ascii=False))')
if [ "$violations" = "[]" ]; then
  echo "ほかの配信元のスキーマの参照: ok（違反 0 件）"
else
  echo "ほかの配信元のスキーマの参照: failed（$violations）"
  exit 1
fi
