#!/bin/sh
set -u

# プラグイン dev-docs を入れている Claude Code の設定の場所（plugins を共有している場所は 1 つにまとめる）
list_dirs() {
  for dir in /home/shuhei2441/.claude /home/shuhei2441/.claude-*; do
    file="$dir/plugins/installed_plugins.json"
    if [ -f "$file" ] && grep -q '"dev-docs@dev-docs"' "$file"; then
      echo "$(readlink -f "$dir/plugins") $dir"
    fi
  done | sort -u -k1,1 | cut -d' ' -f2
}

# 入っているプラグインのフックのファイル
hook_of() {
  python3 -c "
import json, sys
data = json.load(open(sys.argv[1] + '/plugins/installed_plugins.json'))
for item in data.get('plugins', {}).get('dev-docs@dev-docs', []):
    print(item['installPath'] + '/hooks/session_start.py')
" "$1"
}

# 前提確認
dirs=$(list_dirs)
if [ -z "$dirs" ]; then
  echo "前提確認: failed（dev-docs を入れた設定の場所が無い）"
  exit 1
fi
echo "前提確認: ok"

# 計画（--dry-run もここを通る）
targets=""
for dir in $dirs; do
  for hook in $(hook_of "$dir"); do
    if grep -q '/_admin/session-start' "$hook" && ! grep -q 'fetch_context' "$hook"; then
      echo "$dir: skipped（$hook は更新済み）"
    else
      echo "$dir: changed（$hook を更新する）"
      targets="$targets $dir"
    fi
  done
done
if [ -z "$targets" ]; then
  echo "プラグインの更新: skipped"
  exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
  echo "プラグインの更新: changed"
  exit 0
fi

# 適用
rc=0
for dir in $(echo "$targets" | tr ' ' '\n' | sort -u); do
  if CLAUDE_CONFIG_DIR="$dir" claude plugin marketplace update dev-docs \
    && CLAUDE_CONFIG_DIR="$dir" claude plugin update dev-docs@dev-docs; then
    echo "$dir の更新: changed"
  else
    echo "$dir の更新: failed"
    rc=1
  fi
done
exit $rc
