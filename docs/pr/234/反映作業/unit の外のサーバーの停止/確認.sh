#!/bin/sh
set -eu

PORT=8781
UNIT=dev-docs.service
MAIN=$(systemctl --user show -p MainPID --value "$UNIT")
OWNER=$(ss -ltnpH "sport = :$PORT" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1)
echo "unit の MainPID: $MAIN"
echo "ポート $PORT を持つプロセス: ${OWNER:-なし}"
if [ -n "$OWNER" ] && [ "$OWNER" = "$MAIN" ]; then
  echo "ポートを持つプロセス: ok"
else
  echo "ポートを持つプロセス: failed"
  exit 1
fi
PREVENT=$(systemctl --user show -p RestartPreventExitStatus --value "$UNIT")
echo "RestartPreventExitStatus の値: $PREVENT"
case " $PREVENT " in
  *" 3 "*) echo "RestartPreventExitStatus: ok" ;;
  *) echo "RestartPreventExitStatus: failed"; exit 1 ;;
esac
SINCE=$(systemctl --user show -p ActiveEnterTimestamp --value "$UNIT")
if journalctl --user -u "$UNIT" --since "$SINCE" --no-pager 2>/dev/null | grep -q "は使用中です"; then
  echo "起動の後のポートの使用中の終了: failed"
  exit 1
fi
echo "起動の後のポートの使用中の終了: ok"
