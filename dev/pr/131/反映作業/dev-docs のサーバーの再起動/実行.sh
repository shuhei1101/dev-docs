#!/bin/sh
set -u

DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
FIXED=src/dev_docs/features/settings/query.py
# 再起動の前に配信していた配信元の一覧を、確認のスクリプトへ渡す
BEFORE="${TMPDIR:-/tmp}/dev-docs-pr131-serving.txt"
STATUS='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"status","arguments":{}}}'
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
if grep -q 'STATE_DIR_ENV' "$DEVELOP/$FIXED"; then
  echo "develop の worktree の修正: ok"
else
  echo "develop の worktree の修正: failed（$FIXED に STATE_DIR_ENV が無い）"
  exit 1
fi
FIXED_AT=$(stat -c %Y "$DEVELOP/$FIXED")
if [ -n "$(server_started)" ]; then
  echo "稼働中のサーバー: ok"
else
  echo "稼働中のサーバー: failed（127.0.0.1:8781 で待ち受けるプロセスが無い）"
  exit 1
fi

# skipped で終わるときも確認が比べられるよう、計画の前に今の配信元の一覧を記録する
if ! sh scripts/dev-docs-server-wait.sh loaded; then
  echo "再起動の前の配信元: failed（読み込みが終わらない）"
  exit 1
fi
curl -s --max-time 60 -X POST http://127.0.0.1:8781/_admin/mcp \
  -H "$HEADERS_ACCEPT" -H "$HEADERS_TYPE" -d "$STATUS" \
  | grep -o '| [a-z0-9-]* | serving' | sort > "$BEFORE"
echo "再起動の前の配信元: ok（$(wc -l < "$BEFORE") 件）"

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
