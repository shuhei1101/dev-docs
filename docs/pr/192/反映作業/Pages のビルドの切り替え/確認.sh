#!/bin/sh
set -eu

build_type=$(gh api repos/shuhei1101/dev-docs/pages --jq .build_type)
if [ "$build_type" = "workflow" ]; then
  echo "build_type（$build_type）: ok"
else
  echo "build_type（$build_type）: failed"
  exit 1
fi
