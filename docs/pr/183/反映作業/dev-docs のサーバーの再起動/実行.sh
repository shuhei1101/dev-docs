#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
LOG="$HOME/.local/state/dev-docs/serve.log"
PATTERN="^$DEVELOP/.venv/bin/python -m dev_docs serve$"

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  echo "引数は無しか --dry-run だけ: $*"
  exit 1
fi
if [ ! -x "$DEVELOP/.venv/bin/python" ]; then
  echo "前提確認: failed"
  ls -l "$DEVELOP/.venv/bin/python" 2>&1
  exit 1
fi
pids=$(pgrep -f "$PATTERN" || true)
count=$(echo "$pids" | grep -c . || true)
if [ "$count" -gt 1 ]; then
  echo "前提確認: failed"
  echo "dev-docs serve が $count 個動いている: $pids"
  exit 1
fi
echo "前提確認: ok"

# 計画（--dry-run もここを通る）
echo "止める dev-docs serve: ${pids:-なし}"
echo "起動する: (cd $DEVELOP && setsid nohup $DEVELOP/.venv/bin/python -m dev_docs serve > $LOG 2>&1 &)"
if [ "${1:-}" = "--dry-run" ]; then
  echo "dev-docs のサーバーの再起動: changed"
  exit 0
fi

# 適用（止める → 起動する）
if [ -n "$pids" ]; then
  kill -TERM "$pids"
  i=0
  while kill -0 "$pids" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
      echo "dev-docs serve の停止: failed"
      echo "kill -TERM $pids の後 60 秒で止まらない"
      exit 1
    fi
    sleep 1
  done
  echo "dev-docs serve の停止: changed"
fi
mkdir -p "$(dirname "$LOG")"
(cd "$DEVELOP" && setsid nohup "$DEVELOP/.venv/bin/python" -m dev_docs serve > "$LOG" 2>&1 < /dev/null &)
i=0
until curl -s -m 2 -o /dev/null http://127.0.0.1:8781/_api/settings/sources; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "dev-docs serve の起動: failed"
    tail -n 20 "$LOG"
    exit 1
  fi
  sleep 1
done
echo "dev-docs serve の起動: changed"
