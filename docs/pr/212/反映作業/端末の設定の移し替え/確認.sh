#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
plan=$(cd "$DEVELOP" && uv run dev-docs migrate --plan --project-index http://127.0.0.1:8786 2>&1)
if [ -z "$plan" ]; then echo "dev-docs の端末の設定の版: ok"; else echo "dev-docs の端末の設定の版: failed"; echo "$plan"; exit 1; fi
ids=$(curl -s -m 10 http://127.0.0.1:8786/settings/sources | python3 -c "import json,sys; print(' '.join(str(s.get('id')) for s in json.load(sys.stdin)['sources']))")
echo "project-index の端末の設定の配信元: $ids"
if [ -n "$ids" ]; then echo "project-index の端末の設定: ok"; else echo "project-index の端末の設定: failed"; exit 1; fi
