#!/bin/sh
set -eu

# develop への push の直近の完了した pages.yml の実行が成功し、全ての step が名前つきで success かを、E2E テストの正常系で確認する
if ! out=$(uv run pytest tests/e2e/workflow/test_pages_yml.py::test_normal -v 2>&1); then
  echo "公開ページの配信の正常系: failed"
  echo "uv run pytest tests/e2e/workflow/test_pages_yml.py::test_normal -v"
  echo "$out"
  exit 1
fi
echo "$out" | tail -1
echo "公開ページの配信の正常系: ok"
