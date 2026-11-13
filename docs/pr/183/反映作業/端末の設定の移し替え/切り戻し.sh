#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_BACKUP="$HOME/.config/project-index/settings.yaml.bak-pr183"
latest=$(ls -1t "$SETTINGS".bak-* 2>/dev/null | head -n 1)
if [ -z "$latest" ] || [ ! -f "$PI_BACKUP" ]; then
  echo "退避したファイル: failed"
  ls -l "$SETTINGS".bak-* "$PI_BACKUP" 2>&1
  exit 1
fi
cp -p "$latest" "$SETTINGS"
echo "dev-docs の端末の設定の書き戻し: changed"

# project-index の端末の設定は、控えの sources を PUT で送り、保存と読み直しを project-index に任せる
body=$("$DEVELOP/.venv/bin/python" -B -c "import json, sys, yaml; print(json.dumps({'sources': yaml.safe_load(open(sys.argv[1], encoding='utf-8')).get('sources') or []}))" "$PI_BACKUP")
expected=$(printf '%s' "$body" | python3 -c "import json, sys; print(' '.join(sorted(str(s.get('id')) for s in json.load(sys.stdin)['sources'])))")
code=$(curl -s -m 60 -o /dev/null -w '%{http_code}' -X PUT http://127.0.0.1:8786/settings/sources \
  -H 'Content-Type: application/json' -d "$body")
if [ "$code" != "200" ]; then
  echo "project-index の端末の設定の書き戻し: failed（PUT /settings/sources が $code）"
  exit 1
fi
actual=$(curl -s -m 10 http://127.0.0.1:8786/settings/sources | python3 -c "import json, sys; print(' '.join(sorted(str(s.get('id')) for s in json.load(sys.stdin)['sources'])))")
if [ "$actual" = "$expected" ]; then
  echo "project-index の端末の設定の書き戻し: changed（$actual）"
else
  echo "project-index の端末の設定の書き戻し: failed（控え: $expected・今: $actual）"
  exit 1
fi
