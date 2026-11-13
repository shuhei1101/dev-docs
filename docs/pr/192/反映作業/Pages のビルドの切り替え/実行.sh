#!/bin/sh
set -eu

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  exit 1
fi
if ! current=$(gh api repos/shuhei1101/dev-docs/pages --jq .build_type 2>&1); then
  echo "前提確認: failed"
  echo "gh api repos/shuhei1101/dev-docs/pages"
  echo "$current"
  exit 1
fi
echo "前提確認: ok"

# 計画（--dry-run もここを通る）
if [ "$current" = "workflow" ]; then
  echo "build_type の切り替え: skipped"
  exit 0
fi
echo "--- repos/shuhei1101/dev-docs/pages build_type"
echo "-$current"
echo "+workflow"
if [ "${1:-}" = "--dry-run" ]; then
  echo "build_type の切り替え: changed"
  exit 0
fi

# 適用
if ! err=$(gh api -X PUT repos/shuhei1101/dev-docs/pages -f build_type=workflow 2>&1); then
  echo "build_type の切り替え: failed"
  echo "gh api -X PUT repos/shuhei1101/dev-docs/pages -f build_type=workflow"
  echo "$err"
  exit 1
fi
echo "build_type の切り替え: changed"
