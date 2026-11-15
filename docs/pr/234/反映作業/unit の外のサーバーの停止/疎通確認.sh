#!/bin/sh
set -eu

if command -v ss >/dev/null 2>&1; then
  echo "ss: ok"
else
  echo "ss: failed"
  exit 1
fi
if MAIN=$(systemctl --user show -p MainPID --value dev-docs.service 2>&1); then
  echo "dev-docs.service の MainPID: ok（$MAIN）"
else
  echo "dev-docs.service の MainPID: failed"
  echo "$MAIN"
  exit 1
fi
