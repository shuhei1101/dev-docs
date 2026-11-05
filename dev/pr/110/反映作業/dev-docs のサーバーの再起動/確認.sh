#!/bin/sh
set -u

BASE=http://127.0.0.1:8781
# aituber の ER 図『キャラクター』（物理名で書いた同じ文書のテーブルへの外部キー characters.character_id を持つ）
ER_DOC="$BASE/_api/sources/aituber/docs/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/ER%E5%9B%B3/%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC.yaml"

rc=0
start=$(curl -s -w ' %{http_code}' -X POST "$BASE/_admin/session-start" \
  -H 'Content-Type: application/json' -d '{"session_id":"reflection-check","reason":"startup"}')
case "$start" in
  *'"forgotten"'*' 200') echo "/_admin/session-start: ok（$start）" ;;
  *) echo "/_admin/session-start: failed（$start）"; rc=1 ;;
esac
for path in /_admin/no-such /_admin/session-context; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE$path" \
    -H 'Content-Type: application/json' -d '{}')
  if [ "$code" = "404" ]; then
    echo "$path への POST: ok（404）"
  else
    echo "$path への POST: failed（$code）"
    rc=1
  fi
done
if curl -s "$ER_DOC" | grep -q '\[characters\.character_id\]('; then
  echo "物理名の外部キーのセルのリンク: ok"
else
  echo "物理名の外部キーのセルのリンク: failed（ER 図『キャラクター』の Markdown に [characters.character_id]( が無い）"
  rc=1
fi
exit $rc
