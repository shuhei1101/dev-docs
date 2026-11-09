#!/bin/sh
set -u

HEADERS_ACCEPT='Accept: application/json, text/event-stream'
HEADERS_TYPE='Content-Type: application/json'
INITIALIZE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"reflection-run","version":"0"}}}'
RESTART='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"restart","arguments":{}}}'

post_code() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8781$1" \
    -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" -d "$2"
}

# 前提確認
if grep -q 'SlashlessMcpPathMiddleware' /mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/src/dev_docs/server/app.py; then
  echo "develop の worktree の修正: ok"
else
  echo "develop の worktree の修正: failed（develop の worktree に SlashlessMcpPathMiddleware が無い）"
  exit 1
fi
if [ "$(post_code /_admin/mcp/ "$INITIALIZE")" = "200" ]; then
  echo "稼働中のサーバー: ok"
else
  echo "稼働中のサーバー: failed"
  exit 1
fi

# 計画
if [ "$(post_code /mcp "$INITIALIZE")" = "200" ]; then
  echo "サーバーの再起動: skipped（/mcp が既に 200）"
  exit 0
fi
echo "再起動するサーバー: 127.0.0.1:8781（/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop の dev-docs serve）"
if [ "${1:-}" = "--dry-run" ]; then
  echo "サーバーの再起動: changed"
  exit 0
fi

# 適用
code=$(post_code /_admin/mcp/ "$RESTART")
if [ "$code" != "200" ]; then
  echo "サーバーの再起動: failed（restart が $code）"
  exit 1
fi
tries=0
until [ "$(post_code /mcp "$INITIALIZE")" = "200" ]; do
  tries=$((tries + 1))
  if [ "$tries" -ge 60 ]; then
    echo "サーバーの再起動: failed（60 秒待っても /mcp が 200 にならない）"
    exit 1
  fi
  sleep 1
done
echo "サーバーの再起動: changed"
