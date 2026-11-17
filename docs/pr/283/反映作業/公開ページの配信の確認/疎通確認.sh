#!/bin/sh
set -eu

# gh が認証済みで、リポジトリの workflow の実行を読み取れるか
if ! out=$(gh run list --repo shuhei1101/dev-docs --workflow pages.yml --limit 1 --json databaseId 2>&1); then
  echo "GitHub Actions の実行の参照: failed"
  echo "gh run list --repo shuhei1101/dev-docs --workflow pages.yml --limit 1 --json databaseId"
  echo "$out"
  exit 1
fi
echo "GitHub Actions の実行の参照: ok"
