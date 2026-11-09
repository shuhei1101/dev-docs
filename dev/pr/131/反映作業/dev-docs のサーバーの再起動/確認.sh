#!/bin/sh
set -u

BEFORE="${TMPDIR:-/tmp}/dev-docs-pr131-serving.txt"
STATUS='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"status","arguments":{}}}'

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

status=$(curl -s --max-time 60 -X POST http://127.0.0.1:8781/_admin/mcp \
  -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d "$STATUS")

# XDG_CONFIG_HOME を設定していない端末なので、端末の設定は今と同じ場所
if printf '%s' "$status" | grep -q "端末の設定: $HOME/.config/dev-docs/settings.yaml"; then
  echo "端末の設定のパス: ok"
else
  echo "端末の設定のパス: failed"
  exit 1
fi

# 再起動の前と同じ配信元を配信している
if [ ! -f "$BEFORE" ]; then
  echo "配信元の一覧: failed（再起動の前の一覧 $BEFORE が無い）"
  exit 1
fi
after=$(printf '%s' "$status" | grep -o '| [a-z0-9-]* | serving' | sort)
if [ "$after" = "$(cat "$BEFORE")" ]; then
  echo "配信元の一覧: ok（$(printf '%s\n' "$after" | wc -l) 件）"
else
  echo "配信元の一覧: failed（再起動の前: $(tr '\n' ' ' < "$BEFORE")／後: $(printf '%s' "$after" | tr '\n' ' ')）"
  exit 1
fi
