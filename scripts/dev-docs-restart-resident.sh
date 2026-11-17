#!/usr/bin/env bash
# AI Monitor の常駐サーバーの restart_command から呼ぶ、dev-docs の常駐サーバーを起動し直すスクリプト。
# 前回起動し直した commit からサーバーが実行時に参照するファイルが変わっていれば、
# 依存を uv.lock どおりにそろえてから dev-docs.service を起動し直し、起動し直した commit を記録する。
#
#   bash scripts/dev-docs-restart-resident.sh
set -euo pipefail

# 変わったら依存をそろえて起動し直す、サーバーが実行時に参照するファイル
RUNTIME_PATHS=(src content templates pyproject.toml uv.lock .python-version)
# 起動し直す systemd --user の unit
UNIT=dev-docs.service
# 状態のフォルダ（dev-docs-server-wait.sh の LOG_DIR と同じ規則。XDG_STATE_HOME は絶対パスでなければ未設定として扱う）
XDG_STATE_HOME=${XDG_STATE_HOME:-}
case "$XDG_STATE_HOME" in /*) ;; *) XDG_STATE_HOME= ;; esac
# 前回起動し直した commit の SHA を 1 行で持つファイル
RECORD_FILE="${DEV_DOCS_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/dev-docs}/restarted-commit"

# スクリプトの実体の親（リポジトリの直下）へ移る
cd "$(dirname "$(readlink -f "$0")")/.."

# 前回起動し直した commit を読み込む
previous=""
if [ -f "$RECORD_FILE" ]; then
    previous="$(head -n 1 "$RECORD_FILE")"
fi
head_sha="$(git rev-parse HEAD)"

# 記録があり、実行時に参照するファイルが変わっていないか
if [ -n "$previous" ] && git diff --quiet "$previous" HEAD -- "${RUNTIME_PATHS[@]}" 2>/dev/null; then
    # 変わっていない: 起動し直さずに記録だけ HEAD へ進める
    printf '%s\n' "$head_sha" > "$RECORD_FILE"
    echo "restart-resident: 実行時に参照するファイルは $previous から変わっていないため、起動し直さない"
    exit 0
fi
# 記録が無い・記録の commit が見つからない・変わった: 依存をそろえて起動し直す

# 依存を uv.lock どおりにそろえる（失敗したらサーバーは今のコードのまま動き続ける）
uv sync --frozen || {
    rc=$?
    echo "restart-resident: uv sync --frozen が終了コード $rc で失敗した" >&2
    exit "$rc"
}

# 常駐サーバーを起動し直す
systemctl --user restart "$UNIT" || {
    rc=$?
    echo "restart-resident: systemctl --user restart $UNIT が終了コード $rc で失敗した" >&2
    exit "$rc"
}

# 起動し直した commit を記録する
mkdir -p "$(dirname "$RECORD_FILE")"
printf '%s\n' "$head_sha" > "$RECORD_FILE"
echo "restart-resident: $head_sha で $UNIT を起動し直した"
