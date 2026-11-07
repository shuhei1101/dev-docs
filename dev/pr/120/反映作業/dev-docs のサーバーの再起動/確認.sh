#!/bin/sh
set -u

# 作業範囲の外の配信元 ai-monitor の件数の検索が、修正の前の 85.3 秒より短い時間で応答するか
REQUEST='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_docs","arguments":{"source":"ai-monitor","outside_scope":true,"view":"count","cwd":"/mnt/c/Users/shuhe/repo/dev-docs"}}}'
start=$(date +%s.%N)
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 85 -X POST http://127.0.0.1:8781/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
  -d "$REQUEST")
end=$(date +%s.%N)
elapsed=$(echo "$end - $start" | bc)
if [ "$code" = "200" ]; then
  echo "ai-monitor の件数の検索: ok（${elapsed} 秒）"
else
  echo "ai-monitor の件数の検索: failed（${elapsed} 秒・HTTP $code）"
  exit 1
fi
