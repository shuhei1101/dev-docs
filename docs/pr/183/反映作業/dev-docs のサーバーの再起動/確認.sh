#!/bin/sh
set -u
code=$(curl -s -m 45 -o /dev/null -w '%{http_code}' http://127.0.0.1:8781/_api/sources/dev-docs/docs || true)
echo "GET /_api/sources/dev-docs/docs: $code"
if [ "$code" = "200" ]; then echo "画面の API の文書の取得: ok"; else echo "画面の API の文書の取得: failed"; exit 1; fi
