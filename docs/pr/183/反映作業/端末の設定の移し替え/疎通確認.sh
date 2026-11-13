#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_SETTINGS="$HOME/.config/project-index/settings.yaml"
rc=0
if out=$(cd "$DEVELOP" && uv run dev-docs migrate --help 2>&1); then echo "dev-docs の develop: ok"; else echo "dev-docs の develop: failed"; echo "$out"; rc=1; fi
if [ -r "$SETTINGS" ]; then echo "dev-docs の端末の設定: ok"; else echo "dev-docs の端末の設定: failed"; rc=1; fi
if [ -r "$PI_SETTINGS" ]; then echo "project-index の端末の設定: ok"; else echo "project-index の端末の設定: failed"; rc=1; fi
code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8786/settings/sources || true)
if [ "$code" = "200" ]; then echo "project-index の端末の設定の API: ok"; else echo "project-index の端末の設定の API: failed"; echo "GET /settings/sources: $code"; rc=1; fi
exit $rc
