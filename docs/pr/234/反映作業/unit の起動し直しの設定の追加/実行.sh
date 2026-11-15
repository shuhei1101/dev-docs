#!/bin/sh
set -eu

TARGET="$HOME/.config/systemd/user/dev-docs.service"
NEW=$(mktemp)
trap 'rm -f "$NEW"' EXIT

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  exit 1
fi
if [ ! -f "$TARGET" ] || ! grep -q '^\[Service\]$' "$TARGET"; then
  echo "前提確認: failed"
  echo "$TARGET に [Service] の節がありません"
  exit 1
fi
echo "前提確認: ok"

# 計画（--dry-run もここを通る）
if grep -q '^RestartPreventExitStatus=.*\b3\b' "$TARGET"; then
  echo "RestartPreventExitStatus の追加: skipped"
  exit 0
fi
# [Service] の節の末尾（次の節の前か、ファイルの末尾）に追加する
awk '
  /^\[/ { if (in_service) { print "RestartPreventExitStatus=3"; added = 1 } in_service = ($0 == "[Service]") }
  /^$/ && in_service && !added { print "RestartPreventExitStatus=3"; added = 1; in_service = 0 }
  { print }
  END { if (in_service && !added) print "RestartPreventExitStatus=3" }
' "$TARGET" > "$NEW"
diff -u --label "$TARGET" --label "$TARGET" "$TARGET" "$NEW" || true
if [ "${1:-}" = "--dry-run" ]; then
  echo "RestartPreventExitStatus の追加: changed"
  echo "daemon-reload: changed"
  exit 0
fi

# 適用（検証 → 退避 → 置き換え → 読み直し）
if [ "$(grep -c '^RestartPreventExitStatus=3$' "$NEW")" != "1" ] \
  || [ "$(grep -v '^RestartPreventExitStatus=3$' "$NEW" | md5sum)" != "$(md5sum < "$TARGET")" ]; then
  echo "検証: failed"
  exit 1
fi
echo "検証: ok"
cp -p "$TARGET" "$TARGET.bak-pr234"
cat "$NEW" > "$TARGET"
echo "RestartPreventExitStatus の追加: changed"
if systemctl --user daemon-reload; then
  echo "daemon-reload: changed"
else
  echo "daemon-reload: failed"
  echo "$ systemctl --user daemon-reload"
  exit 1
fi
