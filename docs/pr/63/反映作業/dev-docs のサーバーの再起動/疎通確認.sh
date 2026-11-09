#!/bin/sh
set -u

if [ -f /mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/src/dev_docs/server/app.py ]; then
  echo "develop の worktree: ok"
else
  echo "develop の worktree: failed"
  exit 1
fi

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8781/_admin/mcp/ \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
if [ "$code" = "200" ]; then
  echo "管理の MCP（/_admin/mcp/）: ok"
else
  echo "管理の MCP（/_admin/mcp/）: failed（$code）"
  exit 1
fi
