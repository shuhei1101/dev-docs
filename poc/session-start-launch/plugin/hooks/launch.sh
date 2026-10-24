#!/usr/bin/env bash
# 8781 が空いていればサーバーを切り離して起動し、すぐに戻る SessionStart のフック。
set -euo pipefail

PORT=8781
SERVER_DIR="${CLAUDE_PLUGIN_ROOT}/../server"
LOG="${POC_LOG:-/tmp/poc-session-start-launch.log}"

echo "hook start $(date +%s.%N)" >> "$LOG"
# 待ち受けているプロセスがあるか
if ss -ltn "sport = :${PORT}" | grep -q LISTEN; then
  # 使用中: 何もしない
  echo "hook skip (port in use)" >> "$LOG"
else
  # 空き: 新しいセッションでサーバーを起動し、フックの終了に巻き込まれないよう切り離す
  cd "$SERVER_DIR"
  setsid nohup uv run uvicorn server:app --host 127.0.0.1 --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
  echo "hook launched pid=$!" >> "$LOG"
fi
echo "hook end $(date +%s.%N)" >> "$LOG"
