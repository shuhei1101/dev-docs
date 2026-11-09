#!/bin/sh
# dev-docs のサーバーの再起動の反映作業が、再起動の後の新しいサーバーを待つ共通のスクリプト。
#
#   sh scripts/dev-docs-server-wait.sh listening {UNIX 時刻}
#     127.0.0.1:8781 で、{UNIX 時刻} 以後に起動したプロセスが待ち受けるまで待つ
#   sh scripts/dev-docs-server-wait.sh loaded
#     管理の MCP の status が loading: false を返す（全ての配信元の読み込みが終わる）まで待つ
#
# 上限は規約『資源の値の決め方』の下流を待つタイムアウト（実測 + 50%）で導いた。
# - 待ち受け: 2026-11-08 の実測 78 秒 + 50% = 117 秒 → 120 秒
# - 読み込み: 2026-11-08 の実測 357 秒・308 秒の最大 + 50% = 536 秒 → 540 秒
set -u

PORT=8781
LISTENING_LIMIT=120
LOADED_LIMIT=540
# status は読み込みを待たずに応答する。1 回の要求は LOADED_LIMIT の残りを超えない
STATUS='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"status","arguments":{"format":"json"}}}'

# 127.0.0.1:8781 で待ち受けるプロセスの起動時刻（UNIX 時刻）。無ければ空
server_started() {
  pid=$(ss -ltnpH "sport = :$PORT" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1)
  [ -n "$pid" ] || return 0
  date -d "$(ps -o lstart= -p "$pid")" +%s
}

wait_listening() {
  since=$1
  start=$(date +%s)
  while :; do
    started=$(server_started)
    if [ -n "$started" ] && [ "$started" -ge "$since" ]; then
      echo "新しいサーバーの待ち受け: ok（$(($(date +%s) - start)) 秒）"
      return 0
    fi
    if [ $(($(date +%s) - start)) -ge "$LISTENING_LIMIT" ]; then
      echo "新しいサーバーの待ち受け: failed（$LISTENING_LIMIT 秒待っても $since 以後に起動したサーバーが待ち受けない）"
      return 1
    fi
    sleep 1
  done
}

wait_loaded() {
  start=$(date +%s)
  while :; do
    left=$((LOADED_LIMIT - ($(date +%s) - start)))
    if [ "$left" -le 0 ]; then
      echo "配信元の読み込み: failed（$LOADED_LIMIT 秒待っても status が loading: false を返さない）"
      return 1
    fi
    body=$(curl -s --max-time "$left" -X POST "http://127.0.0.1:$PORT/_admin/mcp" \
      -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
      -d "$STATUS")
    # structuredContent の loading（text の JSON は字下げつきで、この形に当たらない）
    if printf '%s' "$body" | grep -q '"loading":false'; then
      echo "配信元の読み込み: ok（$(($(date +%s) - start)) 秒）"
      return 0
    fi
    sleep 1
  done
}

case "${1:-}" in
  listening)
    if [ $# -ne 2 ]; then
      echo "引数: failed（listening には UNIX 時刻を 1 つ渡す）"
      exit 1
    fi
    wait_listening "$2"
    ;;
  loaded)
    if [ $# -ne 1 ]; then
      echo "引数: failed（loaded は引数を取らない）"
      exit 1
    fi
    wait_loaded
    ;;
  *)
    echo "引数: failed（listening か loaded を渡す）"
    exit 1
    ;;
esac
