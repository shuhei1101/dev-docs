#!/bin/sh
set -eu

PREVENT=$(systemctl --user show -p RestartPreventExitStatus --value dev-docs.service)
echo "RestartPreventExitStatus の値: $PREVENT"
case " $PREVENT " in
  *" 3 "*) echo "RestartPreventExitStatus: ok" ;;
  *) echo "RestartPreventExitStatus: failed"; exit 1 ;;
esac
EXEC=$(systemctl --user show -p ExecStart --value dev-docs.service)
echo "ExecStart の値: $EXEC"
case "$EXEC" in
  *"/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/.venv/bin/python"*"-m dev_docs serve"*) echo "ExecStart: ok" ;;
  *) echo "ExecStart: failed"; exit 1 ;;
esac
