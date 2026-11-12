#!/bin/sh
# dev-docs のサーバーの再起動の反映作業が、再起動の後の新しいサーバーを待つ共通のスクリプト。
#
#   sh scripts/dev-docs-server-wait.sh listening {UNIX 時刻}
#     127.0.0.1:8781 で、{UNIX 時刻} 以後に起動したサーバーが待ち受けるまで待つ
#   sh scripts/dev-docs-server-wait.sh started
#     127.0.0.1:8781 で待ち受けるサーバーが最後に起動した時刻（UNIX 時刻）を出す
#
# 上限は規約『資源の値の決め方』の下流を待つタイムアウト（実測 + 50%）で導いた。
# - 待ち受け: 2026-11-08 の実測 78 秒 + 50% = 117 秒 → 120 秒
set -u

PORT=8781
# 端末の設定の log_dir の既定（XDG_STATE_HOME は絶対パスでなければ未設定として扱う）
XDG_STATE_HOME=${XDG_STATE_HOME:-}
case "$XDG_STATE_HOME" in /*) ;; *) XDG_STATE_HOME= ;; esac
LOG_DIR="${DEV_DOCS_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/dev-docs}/logs"
LISTENING_LIMIT=120

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
  *)
    echo "引数: failed（listening・started のどちらかを指定する）"
    exit 1
    ;;
esac
