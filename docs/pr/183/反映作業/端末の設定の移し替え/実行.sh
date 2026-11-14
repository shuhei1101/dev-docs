#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_SETTINGS="$HOME/.config/project-index/settings.yaml"
PI_BACKUP="$HOME/.config/project-index/settings.yaml.bak-pr183"
BACKUP="$SETTINGS.bak-pr183"
ADDRESS=http://127.0.0.1:8786

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  echo "引数は無しか --dry-run だけ: $*"
  exit 1
fi
if [ ! -f "$SETTINGS" ] || [ ! -f "$PI_SETTINGS" ] || [ ! -d "$DEVELOP" ]; then
  echo "前提確認: failed"
  ls -l "$SETTINGS" "$PI_SETTINGS" "$DEVELOP" 2>&1
  exit 1
fi
code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' "$ADDRESS/settings/sources" || true)
if [ "$code" != "200" ]; then
  echo "前提確認: failed"
  echo "GET $ADDRESS/settings/sources: $code"
  exit 1
fi
echo "前提確認: ok"

# 計画（--dry-run もここを通る）
if ! plan=$(cd "$DEVELOP" && uv run dev-docs migrate --plan --project-index "$ADDRESS" 2>&1); then
  echo "計画: failed"
  echo "$plan"
  exit 1
fi
if [ -z "$plan" ]; then
  echo "端末の設定の移し替え: skipped"
  exit 0
fi
echo "$plan"
if [ "${1:-}" = "--dry-run" ]; then
  echo "端末の設定の移し替え: changed"
  exit 0
fi

# 適用（両方の端末の設定を退避してから移し替える。切り戻しはこの 2 つの控えだけを書き戻す）
cp -p "$SETTINGS" "$BACKUP"
echo "dev-docs の端末の設定の退避: changed"
cp -p "$PI_SETTINGS" "$PI_BACKUP"
echo "project-index の端末の設定の退避: changed"
if ! out=$(cd "$DEVELOP" && uv run dev-docs migrate --project-index "$ADDRESS" 2>&1); then
  echo "端末の設定の移し替え: failed"
  echo "$out"
  exit 1
fi
echo "$out"
echo "端末の設定の移し替え: changed"
