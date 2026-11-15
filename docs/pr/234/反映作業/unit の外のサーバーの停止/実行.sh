#!/bin/sh
set -eu

PORT=8781
UNIT=dev-docs.service
# 起動し直す前のプロセスの停止を待つ上限（restart の停止の待ちの上限 67.5 秒に余裕を足した値）
STOP_WAIT_SEC=80
# 起動から待ち受けまでの待ちの上限
START_WAIT_SEC=30

listener_pid() {
  ss -ltnpH "sport = :$PORT" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1
}

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  exit 1
fi
PREVENT=$(systemctl --user show -p RestartPreventExitStatus --value "$UNIT")
case " $PREVENT " in
  *" 3 "*) echo "前提確認: ok" ;;
  *)
    # 前の作業で満たす前提なので、--dry-run では missing として計画へ進み、適用では止める
    if [ "${1:-}" = "--dry-run" ]; then
      echo "前提確認: missing"
      echo "$UNIT の RestartPreventExitStatus に 3 がありません（作業「unit の起動し直しの設定の追加」が先）"
    else
      echo "前提確認: failed"
      echo "$UNIT の RestartPreventExitStatus に 3 がありません（作業「unit の起動し直しの設定の追加」が先）"
      exit 1
    fi
    ;;
esac

# 計画（--dry-run もここを通る）
MAIN=$(systemctl --user show -p MainPID --value "$UNIT")
OWNER=$(listener_pid)
echo "unit の MainPID: $MAIN"
echo "ポート $PORT を持つプロセス: ${OWNER:-なし}"
if [ -n "$OWNER" ] && [ "$OWNER" = "$MAIN" ]; then
  echo "unit の外のプロセスの停止: skipped"
  echo "unit の起動し直し: skipped"
  exit 0
fi
if [ -n "$OWNER" ]; then
  CMD=$(tr '\0' ' ' < "/proc/$OWNER/cmdline")
  echo "停止するプロセス: $OWNER $CMD"
  case "$CMD" in
    *"-m dev_docs serve"*) ;;
    *)
      echo "停止するプロセスの確認: failed"
      echo "ポート $PORT を持つプロセスが dev-docs serve ではありません"
      exit 1
      ;;
  esac
fi
if [ "${1:-}" = "--dry-run" ]; then
  [ -n "$OWNER" ] && echo "unit の外のプロセスの停止: changed" || echo "unit の外のプロセスの停止: skipped"
  echo "unit の起動し直し: changed"
  exit 0
fi

# 適用
if [ -n "$OWNER" ]; then
  kill -TERM "$OWNER"
  WAITED=0
  while [ -n "$(listener_pid)" ] && [ "$WAITED" -lt "$STOP_WAIT_SEC" ]; do
    sleep 1
    WAITED=$((WAITED + 1))
  done
  if [ -n "$(listener_pid)" ]; then
    echo "unit の外のプロセスの停止: failed"
    echo "$ kill -TERM $OWNER"
    exit 1
  fi
  echo "unit の外のプロセスの停止: changed"
fi
systemctl --user reset-failed "$UNIT" 2>/dev/null || true
if ! systemctl --user restart "$UNIT"; then
  echo "unit の起動し直し: failed"
  echo "$ systemctl --user restart $UNIT"
  exit 1
fi
WAITED=0
while [ "$(listener_pid)" != "$(systemctl --user show -p MainPID --value "$UNIT")" ] && [ "$WAITED" -lt "$START_WAIT_SEC" ]; do
  sleep 1
  WAITED=$((WAITED + 1))
done
if [ "$(listener_pid)" = "$(systemctl --user show -p MainPID --value "$UNIT")" ]; then
  echo "unit の起動し直し: changed"
else
  echo "unit の起動し直し: failed"
  echo "$ systemctl --user status $UNIT"
  systemctl --user status "$UNIT" --no-pager 2>&1 | head -n 20 || true
  exit 1
fi
