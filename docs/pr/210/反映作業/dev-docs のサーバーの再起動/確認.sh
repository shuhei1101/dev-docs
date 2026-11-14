#!/bin/sh
set -u

# 端末の設定の取得が内容のバージョン（version）を返すか
body=$(curl -s -m 45 http://127.0.0.1:8781/_api/settings/sources || true)
if printf '%s' "$body" | grep -q '"version":"[^"]'; then
  echo "端末の設定の取得の version: ok"
else
  echo "端末の設定の取得の version: failed（応答に version が無い: $(printf '%s' "$body" | head -c 200)）"
  exit 1
fi

# インターフェース定義の文書の図が map の範囲で、廃止した部品の範囲が無いか
markdown=$(curl -s -m 45 http://127.0.0.1:8781/_api/sources/dev-docs/docs/docs/interface/IF-155-19 || true)
maps=$(printf '%s' "$markdown" | grep -o '<!-- map: ' | wc -l)
retired=$(printf '%s' "$markdown" | grep -oE '<!-- (flow|sequence|er) -->' | wc -l)
if [ "$maps" -gt 0 ] && [ "$retired" -eq 0 ]; then
  echo "文書の取得の図: ok（map の範囲 $maps 個、廃止した部品の範囲 0 個）"
else
  echo "文書の取得の図: failed（map の範囲 $maps 個、廃止した部品の範囲 $retired 個）"
  exit 1
fi
