#!/bin/sh
set -u

HEADERS_ACCEPT='Accept: application/json, text/event-stream'
HEADERS_TYPE='Content-Type: application/json'
INITIALIZE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"reflection-run","version":"0"}}}'
RESTART='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"restart","arguments":{}}}'
TOOLS_LIST='{"jsonrpc":"2.0","id":3,"method":"tools/list"}'

post_code() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8781$1" \
    -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" -d "$2"
}

# 新しいコードのサーバーは、write_docs の description に unchecked の説明を持つ
running_new() {
  curl -s -X POST http://127.0.0.1:8781/mcp -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" \
    -d "$TOOLS_LIST" | grep -q 'unchecked に返却する'
}

# 前提確認
if [ -f /mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/src/dev_docs/integrations/mdmark.py ]; then
  echo "develop の worktree の修正: ok"
else
  echo "develop の worktree の修正: failed（develop の worktree に src/dev_docs/integrations/mdmark.py が無い）"
  exit 1
fi
if [ "$(post_code /_admin/mcp "$INITIALIZE")" = "200" ]; then
  echo "稼働中のサーバー: ok"
else
  echo "稼働中のサーバー: failed"
  exit 1
fi

# 計画
if running_new; then
  echo "サーバーの再起動: skipped（write_docs の description に unchecked の説明が既にある）"
  exit 0
fi
echo "再起動するサーバー: 127.0.0.1:8781（/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop の dev-docs serve）"
if [ "${1:-}" = "--dry-run" ]; then
  echo "サーバーの再起動: changed"
  exit 0
fi

# 適用
code=$(post_code /_admin/mcp "$RESTART")
if [ "$code" != "200" ]; then
  echo "サーバーの再起動: failed（restart が $code）"
  exit 1
fi
tries=0
until running_new; do
  tries=$((tries + 1))
  if [ "$tries" -ge 60 ]; then
    echo "サーバーの再起動: failed（60 秒待っても write_docs の description に unchecked の説明が入らない）"
    exit 1
  fi
  sleep 1
done
echo "サーバーの再起動: changed"
