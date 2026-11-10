#!/bin/sh
set -u

if command -v claude >/dev/null 2>&1; then
  echo "claude コマンド: ok"
else
  echo "claude コマンド: failed"
  exit 1
fi
if git ls-remote https://github.com/shuhei1101/dev-docs.git develop >/dev/null 2>&1; then
  echo "マーケットプレイス dev-docs（develop）: ok"
else
  echo "マーケットプレイス dev-docs（develop）: failed"
  exit 1
fi
