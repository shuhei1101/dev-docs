#!/bin/sh
set -u

DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
FIXED=src/dev_docs/features/search/types.py
HEADERS_ACCEPT='Accept: application/json, text/event-stream'
HEADERS_TYPE='Content-Type: application/json'
RESTART='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"restart","arguments":{}}}'

# 127.0.0.1:8781 で待ち受けるサーバーが最後に起動した時刻（UNIX 時刻）。無ければ空
server_started() {
  sh scripts/dev-docs-server-wait.sh started 2>/dev/null
}

# 新しいコードのサーバーは、develop の worktree の修正したファイルが更新された後に起動している
running_new() {
  started=$(server_started)
  [ -n "$started" ] && [ "$started" -gt "$FIXED_AT" ]
}

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed（引数は無しか --dry-run だけ）"
  exit 1
fi
if grep -q '該当した行の前に返却する行の数' "$DEVELOP/$FIXED"; then
  echo "develop の worktree の修正: ok"
else
  echo "develop の worktree の修正: failed（$FIXED に修正後の文言が無い）"
  exit 1
fi
FIXED_AT=$(stat -c %Y "$DEVELOP/$FIXED")
if [ -n "$(server_started)" ]; then
  echo "稼働中のサーバー: ok"
else
  echo "稼働中のサーバー: failed（127.0.0.1:8781 で待ち受けていないか、ログに待ち受けを始めた行が無い）"
  exit 1
fi

# 計画
if running_new; then
  echo "サーバーの再起動: skipped（develop の worktree の $FIXED の更新より後に起動している）"
  exit 0
fi
echo "再起動するサーバー: 127.0.0.1:8781（$DEVELOP の dev-docs serve）"
if [ "${1:-}" = "--dry-run" ]; then
  echo "サーバーの再起動: changed"
  exit 0
fi

# 適用
requested=$(date +%s)
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8781/_admin/mcp \
  -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" -d "$RESTART")
if [ "$code" != "200" ]; then
  echo "サーバーの再起動: failed（restart が $code）"
  exit 1
fi
if ! sh scripts/dev-docs-server-wait.sh listening "$requested"; then
  echo "サーバーの再起動: failed（修正の後に起動したサーバーが待ち受けない）"
  exit 1
fi
echo "サーバーの再起動: changed"
