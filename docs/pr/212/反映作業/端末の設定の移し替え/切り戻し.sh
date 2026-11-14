#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
BACKUP="$SETTINGS.bak-pr212"
PI_BACKUP="$HOME/.config/project-index/settings.yaml.bak-pr212"
ADDRESS=http://127.0.0.1:8786
if [ ! -f "$BACKUP" ] || [ ! -f "$PI_BACKUP" ]; then
  echo "退避したファイル: failed"
  ls -l "$BACKUP" "$PI_BACKUP" 2>&1
  exit 1
fi
cp -p "$BACKUP" "$SETTINGS"
echo "dev-docs の端末の設定の書き戻し: changed"

# project-index の端末の設定は、控えの sources を PUT で送り、保存と読み直しを project-index に任せる
# 控えは develop の .venv にある ruamel.yaml で読む
if ! body=$("$DEVELOP/.venv/bin/python" -B -c "import json, sys
from ruamel.yaml import YAML
data = YAML(typ='safe').load(open(sys.argv[1], encoding='utf-8')) or {}
print(json.dumps({'sources': data.get('sources') or []}))" "$PI_BACKUP" 2>&1); then
  echo "project-index の端末の設定の書き戻し: failed（控えを読めない）"
  echo "$body"
  exit 1
fi
ids() { python3 -c "import json, sys; print(' '.join(sorted(str(s.get('id')) for s in json.load(sys.stdin)['sources'])))"; }
expected=$(printf '%s' "$body" | ids)
# 保存の応答は配信元の読み直しを待つため、打ち切られても取得し直して確かめる
code=$(curl -s -m 60 -o /dev/null -w '%{http_code}' -X PUT "$ADDRESS/settings/sources" \
  -H 'Content-Type: application/json' -d "$body" || true)
actual=$(curl -s -m 10 "$ADDRESS/settings/sources" | ids)
if [ "$actual" = "$expected" ]; then
  echo "project-index の端末の設定の書き戻し: changed（$actual）"
else
  echo "project-index の端末の設定の書き戻し: failed（PUT /settings/sources が $code・控え: $expected・今: $actual）"
  exit 1
fi
