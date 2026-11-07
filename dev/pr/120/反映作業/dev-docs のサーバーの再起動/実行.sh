#!/bin/sh
set -u

DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
FIXED=src/dev_docs/features/access/service.py
HEADERS_ACCEPT='Accept: application/json, text/event-stream'
HEADERS_TYPE='Content-Type: application/json'
RESTART='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"restart","arguments":{}}}'

# 127.0.0.1:8781 で待ち受けるプロセスの起動時刻（UNIX 時刻）。無ければ空
server_started() {
  pid=$(ss -ltnpH 'sport = :8781' 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1)
  [ -n "$pid" ] || return 0
  date -d "$(ps -o lstart= -p "$pid")" +%s
}

# 新しいコードのサーバーは、修正を入れた commit より後に起動している
running_new() {
  started=$(server_started)
  [ -n "$started" ] && [ "$started" -gt "$FIXED_AT" ]
}

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed（引数は無しか --dry-run だけ）"
  exit 1
fi
if grep -q '_revision_target' "$DEVELOP/$FIXED"; then
  echo "develop の worktree の修正: ok"
else
  echo "develop の worktree の修正: failed（$FIXED に _revision_target が無い）"
  exit 1
fi
FIXED_AT=$(git -C "$DEVELOP" log -1 --format=%ct -S _revision_target -- "$FIXED")
if [ -z "$FIXED_AT" ]; then
  echo "修正の commit: failed（develop に _revision_target を入れた commit が無い）"
  exit 1
fi
if [ -n "$(server_started)" ]; then
  echo "稼働中のサーバー: ok"
else
  echo "稼働中のサーバー: failed（127.0.0.1:8781 で待ち受けるプロセスが無い）"
  exit 1
fi

# 計画
if running_new; then
  echo "サーバーの再起動: skipped（修正を入れた commit より後に起動している）"
  exit 0
fi
echo "再起動するサーバー: 127.0.0.1:8781（$DEVELOP の dev-docs serve）"
if [ "${1:-}" = "--dry-run" ]; then
  echo "サーバーの再起動: changed"
  exit 0
fi

# 適用
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8781/_admin/mcp \
  -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" -d "$RESTART")
if [ "$code" != "200" ]; then
  echo "サーバーの再起動: failed（restart が $code）"
  exit 1
fi
tries=0
until running_new; do
  tries=$((tries + 1))
  if [ "$tries" -ge 60 ]; then
    echo "サーバーの再起動: failed（60 秒待っても修正の後に起動したサーバーが待ち受けない）"
    exit 1
  fi
  sleep 1
done
echo "サーバーの再起動: changed"
