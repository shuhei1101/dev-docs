#!/bin/sh
set -eu

# legacy（develop の /docs）へ戻す
if ! err=$(gh api -X PUT repos/shuhei1101/dev-docs/pages -f build_type=legacy -f 'source[branch]=develop' -f 'source[path]=/docs' 2>&1); then
  echo "build_type の書き戻し: failed"
  echo "gh api -X PUT repos/shuhei1101/dev-docs/pages -f build_type=legacy -f source[branch]=develop -f source[path]=/docs"
  echo "$err"
  exit 1
fi
echo "build_type の書き戻し: changed"
