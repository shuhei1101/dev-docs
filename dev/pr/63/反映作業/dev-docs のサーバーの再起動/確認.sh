#!/bin/sh
set -u

INITIALIZE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"reflection-check","version":"0"}}}'
rc=0
for path in /mcp /_admin/mcp; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8781$path" \
    -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' \
    -d "$INITIALIZE")
  if [ "$code" = "200" ]; then
    echo "$path への initialize: ok（$code）"
  else
    echo "$path への initialize: failed（$code）"
    rc=1
  fi
done
exit $rc
