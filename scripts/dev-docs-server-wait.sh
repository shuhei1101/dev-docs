#!/bin/sh
# dev-docs のサーバーの再起動の反映作業が、再起動の後の新しいサーバーを待つ共通のスクリプト。
#
#   sh scripts/dev-docs-server-wait.sh listening {UNIX 時刻}
#     127.0.0.1:8781 で、{UNIX 時刻} 以後に起動したサーバーが待ち受けるまで待つ
#   sh scripts/dev-docs-server-wait.sh started
#     127.0.0.1:8781 で待ち受けるサーバーが最後に起動した時刻（UNIX 時刻）を出す
#   sh scripts/dev-docs-server-wait.sh loaded
#     配信元の読み込みが終わり、文書の MCP の describe が応答するまで待つ
#
# 上限は規約『資源の値の決め方』の下流を待つタイムアウト（実測 + 50%）で導いた。
# - 待ち受け: 2026-11-08 の実測 78 秒 + 50% = 117 秒 → 120 秒
# - 読み込み: 2026-11-08 の実測 357 秒・308 秒の最大 + 50% = 536 秒 → 540 秒
set -u

PORT=8781
# 端末の設定の log_dir の既定
LOG_DIR="$HOME/.local/state/dev-docs/logs"
LISTENING_LIMIT=120
LOADED_LIMIT=540
# 読み込み中の describe は読み込みの終わりまで応答しないため、1 回の要求を LOADED_TRY 秒で切って送り直す。
# 読み込みの後の describe の実測 1.1 秒 + 50% = 1.7 秒を下限とし、送り直す回数を抑えるため 30 秒にした
# （実測は 2026-11-08 の 2 回だけの仮の値で、p99.9 を測る作業が残る）。
# 1 回の要求は LOADED_LIMIT の残りを超えない
LOADED_TRY=30
DESCRIBE='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"describe","arguments":{}}}'

# 127.0.0.1:8781 で待ち受けるサーバーが最後に起動した時刻（UNIX 時刻）。待ち受けていなければ空。
# 再起動は os.execv で同じプロセスを置き換え、PID も ps の起動時刻も変わらないため、
# ログの uvicorn が待ち受けを始めた行の最後の時刻を使用する。
# 同じログに記録する複数のプロセスが回転させ、ファイル名の順と時刻の順が一致しないため、行の先頭の時刻で並べ替える
server_started() {
  [ -n "$(ss -ltnH "sport = :$PORT" 2>/dev/null)" ] || return 0
  line=$(for file in "$LOG_DIR/dev-docs.log.3" "$LOG_DIR/dev-docs.log.2" "$LOG_DIR/dev-docs.log.1" "$LOG_DIR/dev-docs.log"; do
    [ -f "$file" ] && grep -a "Uvicorn running on http://127.0.0.1:$PORT " "$file"
  done | sort | tail -n 1)
  [ -n "$line" ] || return 0
  date -d "$(printf '%s' "$line" | cut -c 1-19)" +%s
}

print_started() {
  started=$(server_started)
  if [ -z "$started" ]; then
    echo "サーバーの起動時刻: failed（127.0.0.1:$PORT で待ち受けていないか、$LOG_DIR に待ち受けを始めた行が無い）" >&2
    return 1
  fi
  echo "$started"
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
      echo "配信元の読み込み: failed（$LOADED_LIMIT 秒待っても describe が応答しない）"
      return 1
    fi
    try=$LOADED_TRY
    [ "$left" -lt "$try" ] && try=$left
    body=$(curl -s --max-time "$try" -X POST "http://127.0.0.1:$PORT/mcp" \
      -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
      -d "$DESCRIBE")
    if printf '%s' "$body" | grep -q '"isError":false'; then
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
  started)
    if [ $# -ne 1 ]; then
      echo "引数: failed（started は引数を取らない）"
      exit 1
    fi
    print_started
    ;;
  loaded)
    if [ $# -ne 1 ]; then
      echo "引数: failed（loaded は引数を取らない）"
      exit 1
    fi
    wait_loaded
    ;;
  *)
    echo "引数: failed（listening・started・loaded のどれかを指定する）"
    exit 1
    ;;
esac
