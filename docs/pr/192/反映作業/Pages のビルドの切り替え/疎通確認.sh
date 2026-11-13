#!/bin/sh
set -eu

# Pages の設定を読み取れるか
if out=$(gh api repos/shuhei1101/dev-docs/pages --jq .build_type 2>&1); then
  echo "Pages の設定（build_type=$out）: ok"
else
  echo "Pages の設定: failed"
  echo "gh api repos/shuhei1101/dev-docs/pages"
  echo "$out"
  exit 1
fi

# 管理者の権限があるか（build_type の変更に要る）
admin=$(gh api repos/shuhei1101/dev-docs --jq .permissions.admin 2>&1) || admin="$admin"
if [ "$admin" = "true" ]; then
  echo "管理者の権限: ok"
else
  echo "管理者の権限: failed"
  echo "gh api repos/shuhei1101/dev-docs --jq .permissions.admin"
  echo "$admin"
  exit 1
fi
