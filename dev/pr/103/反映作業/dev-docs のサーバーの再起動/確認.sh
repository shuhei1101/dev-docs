#!/bin/sh
set -u

rc=0
start=$(curl -s -w ' %{http_code}' -X POST http://127.0.0.1:8781/_admin/session-start \
  -H 'Content-Type: application/json' -d '{"session_id":"reflection-check","reason":"startup"}')
case "$start" in
  *'"forgotten"'*' 200') echo "/_admin/session-start: ok（$start）" ;;
  *) echo "/_admin/session-start: failed（$start）"; rc=1 ;;
esac
old=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8781/_admin/session-context \
  -H 'Content-Type: application/json' -d '{"cwd":"/"}')
if [ "$old" = "404" ]; then
  echo "/_admin/session-context: ok（404）"
else
  echo "/_admin/session-context: failed（$old）"
  rc=1
fi
exit $rc
