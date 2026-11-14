#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_SETTINGS="$HOME/.config/project-index/settings.yaml"
PI_BACKUP="$HOME/.config/project-index/settings.yaml.bak-pr212"
BACKUP="$SETTINGS.bak-pr212"
ADDRESS=http://127.0.0.1:8786
FIXED=src/dev_docs/features/migrate/service.py
# 稼働中の project-index のサーバーが PUT /settings/sources の expectedVersion を受け付けるか。
# 今の内容のバージョンと一致しない expectedVersion を付けて PUT し、409（書き込まない）なら受け付ける。
# 受け付けない古いバージョンは 400（expectedVersion: Extra inputs are not permitted）を返す。
probe_expected_version() {
  probe_out=$(mktemp)
  probe_code=$(curl -s -m 30 -o "$probe_out" -w '%{http_code}' -X PUT "$ADDRESS/settings/sources" \
    -H 'Content-Type: application/json' -d '{"sources": [], "expectedVersion": "dev-docs-pr212-probe"}' || true)
  probe_body=$(cat "$probe_out"); rm -f "$probe_out"
  if [ "$probe_code" = "409" ]; then
    echo "project-index のサーバーの expectedVersion: ok"
    return 0
  fi
  echo "project-index のサーバーの expectedVersion: failed（PUT /settings/sources が $probe_code。expectedVersion を受け付けるバージョン（project-index の develop の 7177d39 以降）で起動し直してから依頼元へ返す）"
  echo "$probe_body"
  return 1
}

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
if ! grep -q '"enabled", "scope", "outside_read"' "$DEVELOP/$FIXED"; then
  echo "前提確認: failed"
  echo "$DEVELOP/$FIXED が outside_read で送信しない（作業 PR #212 のマージの前）"
  exit 1
fi
if ! probe_expected_version; then
  echo "前提確認: failed"
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
