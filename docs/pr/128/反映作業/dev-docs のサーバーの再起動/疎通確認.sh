#!/bin/sh
set -u

if [ -d /mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/src/dev_docs ]; then
  echo "develop の worktree: ok"
else
  echo "develop の worktree: failed"
  exit 1
fi

for path in /_admin/mcp /mcp; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8781$path" \
    -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  if [ "$code" = "200" ]; then
    echo "MCP（$path）: ok"
  else
    echo "MCP（$path）: failed（$code）"
    exit 1
  fi
done
