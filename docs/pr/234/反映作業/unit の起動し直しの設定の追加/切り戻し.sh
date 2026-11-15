#!/bin/sh
set -eu

TARGET="$HOME/.config/systemd/user/dev-docs.service"
if [ ! -f "$TARGET.bak-pr234" ]; then
  echo "退避したファイル: failed"
  exit 1
fi
cp -p "$TARGET.bak-pr234" "$TARGET"
echo "unit の書き戻し: changed"
systemctl --user daemon-reload
echo "daemon-reload: changed"
