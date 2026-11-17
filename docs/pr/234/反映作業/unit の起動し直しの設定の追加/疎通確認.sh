#!/bin/sh
set -eu

if systemctl --user show-environment >/dev/null 2>&1; then
  echo "systemd --user: ok"
else
  echo "systemd --user: failed"
  echo "$ systemctl --user show-environment"
  systemctl --user show-environment 2>&1 || true
  exit 1
fi
if [ -f "$HOME/.config/systemd/user/dev-docs.service" ]; then
  echo "dev-docs.service のファイル: ok"
else
  echo "dev-docs.service のファイル: failed"
  exit 1
fi
