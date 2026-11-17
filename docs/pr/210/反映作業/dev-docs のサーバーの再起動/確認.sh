#!/bin/sh
set -u

BASE=http://127.0.0.1:8781
# 1 回の取得の打ち切り。サーバーが project-index を待つ上限
# （src/dev_docs/integrations/project_index/client.py の PROJECT_INDEX_TIMEOUT_SEC 45 秒）+ 50% = 67.5 秒 → 70 秒
TRY_LIMIT=70
# fetch_until_ok の 1 回の呼び出しで再取得を続ける上限。前のプロセスの graceful shutdown の上限
# （src/dev_docs/main.py の PROJECT_INDEX_TIMEOUT_SEC 45 × SHUTDOWN_WAIT_FACTOR 1.5 = 67 秒）+ TRY_LIMIT 70 秒 + 50% ≈ 206 秒 → 210 秒
DEADLINE=210

BODY=$(mktemp)
ERR=$(mktemp)
trap 'rm -f "$BODY" "$ERR"' EXIT

# $1 の URL を HTTP 200 で空でない本文を返却するまで再取得する。本文は $BODY、最後の HTTP の状態は $code、最後の打ち切りは $limit に入る
fetch_until_ok() {
  url=$1
  start=$(date +%s)
  interval=2
  while :; do
    left=$((DEADLINE - ($(date +%s) - start)))
    limit=$TRY_LIMIT
    [ "$left" -lt "$limit" ] && limit=$left
    [ "$limit" -gt 0 ] || return 1
    code=$(curl -sS -m "$limit" -o "$BODY" -w '%{http_code}' "$url" 2>"$ERR")
    if [ "$code" = "200" ] && [ -s "$BODY" ]; then
      return 0
    fi
    left=$((DEADLINE - ($(date +%s) - start)))
    if [ "$left" -le "$interval" ]; then
      return 1
    fi
    sleep "$interval"
    interval=$((interval * 2))
    [ "$interval" -gt 30 ] && interval=30
  done
}

# failed の行の後に、実行したコマンドと最後の HTTP の状態・応答の先頭 200 字・stderr を出す
print_failure() {
  echo "コマンド: curl -sS -m $limit $1"
  echo "HTTP の状態: $code"
  echo "応答の先頭: $(head -c 200 "$BODY")"
  echo "stderr: $(cat "$ERR")"
}

# 端末の設定の取得が内容のバージョン（version）を返すか
URL="$BASE/_api/settings/sources"
if ! fetch_until_ok "$URL"; then
  echo "端末の設定の取得: failed（$DEADLINE 秒再取得しても HTTP 200 で本文を返却しない）"
  print_failure "$URL"
  exit 1
fi
if grep -q '"version":"[^"]' "$BODY"; then
  echo "端末の設定の取得の version: ok"
else
  echo "端末の設定の取得の version: failed（応答に version が無い）"
  print_failure "$URL"
  exit 1
fi

# インターフェース定義の文書の図が map の範囲で、廃止した部品の範囲が無いか
URL="$BASE/_api/sources/dev-docs/docs/docs/interface/IF-155-19"
if ! fetch_until_ok "$URL"; then
  echo "文書の取得: failed（$DEADLINE 秒再取得しても HTTP 200 で本文を返却しない）"
  print_failure "$URL"
  exit 1
fi
maps=$(grep -o '<!-- map: ' "$BODY" | wc -l)
retired=$(grep -oE '<!-- (flow|sequence|er) -->' "$BODY" | wc -l)
if [ "$maps" -gt 0 ] && [ "$retired" -eq 0 ]; then
  echo "文書の取得の図: ok（map の範囲 $maps 個、廃止した部品の範囲 0 個）"
else
  echo "文書の取得の図: failed（map の範囲 $maps 個、廃止した部品の範囲 $retired 個）"
  print_failure "$URL"
  exit 1
fi
