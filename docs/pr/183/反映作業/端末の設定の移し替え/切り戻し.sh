#!/bin/sh
set -u
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_SETTINGS="$HOME/.config/project-index/settings.yaml"
PI_BACKUP="$HOME/.config/project-index/settings.yaml.bak-pr183"
latest=$(ls -1t "$SETTINGS".bak-* 2>/dev/null | head -n 1)
if [ -z "$latest" ] || [ ! -f "$PI_BACKUP" ]; then
  echo "退避したファイル: failed"
  ls -l "$SETTINGS".bak-* "$PI_BACKUP" 2>&1
  exit 1
fi
cp -p "$latest" "$SETTINGS"
echo "dev-docs の端末の設定の書き戻し: changed"
cp -p "$PI_BACKUP" "$PI_SETTINGS"
echo "project-index の端末の設定の書き戻し: changed"
