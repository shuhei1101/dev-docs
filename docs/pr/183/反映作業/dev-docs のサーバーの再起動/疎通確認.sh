#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
rc=0
if [ -x "$DEVELOP/.venv/bin/python" ]; then echo "dev-docs の develop の環境: ok"; else echo "dev-docs の develop の環境: failed"; rc=1; fi
pids=$(pgrep -f "^$DEVELOP/.venv/bin/python -m dev_docs serve$" || true)
echo "稼働中の dev-docs serve: ${pids:-なし}"
echo "稼働中の dev-docs serve の確認: ok"
code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8786/sources || true)
if [ "$code" = "200" ]; then echo "project-index の読み取り API: ok"; else echo "project-index の読み取り API: failed"; echo "GET /sources: $code"; rc=1; fi
exit $rc
