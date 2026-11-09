#!/bin/sh
set -u

DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
FIXED=src/dev_docs/features/convert/decisions.py

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# 稼働中のサーバーが、develop の worktree の decisions.py の更新より後に起動しているか
pid=$(ss -ltnpH 'sport = :8781' 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1)
if [ -z "$pid" ] || [ ! -f "$DEVELOP/$FIXED" ]; then
  echo "新しいコードのサーバー: failed（待ち受けるプロセスか $FIXED が無い）"
  exit 1
fi
started=$(date -d "$(ps -o lstart= -p "$pid")" +%s)
fixed_at=$(stat -c %Y "$DEVELOP/$FIXED")
if [ "$started" -gt "$fixed_at" ]; then
  echo "新しいコードのサーバー: ok（起動 $started > 更新 $fixed_at）"
else
  echo "新しいコードのサーバー: failed（起動 $started <= 更新 $fixed_at）"
  exit 1
fi

# 配信元 ai-monitor の ER 図『セッション』が、新しいコードの変換で 200 で返るか
DOC=dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/ER%E5%9B%B3/%E3%82%BB%E3%83%83%E3%82%B7%E3%83%A7%E3%83%B3.yaml
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "http://127.0.0.1:8781/_api/sources/ai-monitor/docs/$DOC")
if [ "$code" = "200" ]; then
  echo "ER 図『セッション』の取得: ok"
else
  echo "ER 図『セッション』の取得: failed（HTTP $code）"
  exit 1
fi
