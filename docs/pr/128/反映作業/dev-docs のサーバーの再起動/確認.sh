#!/bin/sh
set -u

if ! sh scripts/dev-docs-server-wait.sh loaded; then
  exit 1
fi

# 配信元 ai-monitor の ER 図『セッション』の関連が、両端の列と多重度つきで ER 図の部品の定義に出るか
DOC=dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/ER%E5%9B%B3/%E3%82%BB%E3%83%83%E3%82%B7%E3%83%A7%E3%83%B3.yaml
response=$(curl -s -w '\n%{http_code}' --max-time 60 "http://127.0.0.1:8781/_api/sources/ai-monitor/docs/$DOC")
code=$(printf '%s' "$response" | tail -n 1)
body=$(printf '%s' "$response" | sed '$d')
if [ "$code" != "200" ]; then
  echo "ER 図『セッション』の取得: failed（HTTP $code）"
  exit 1
fi
echo "ER 図『セッション』の取得: ok"
relations=$(printf '%s' "$body" | python3 -c '
import json, re, sys
markdown = json.load(sys.stdin)["markdown"]
match = re.search(r"<!-- er -->\n\n```json\n(.*?)\n```", markdown, re.S)
if match is None:
    sys.exit(1)
for relation in json.loads(match.group(1))["relations"]:
    print(relation["fromColumn"], relation["fromCard"], relation["toColumn"], relation["toCard"])
')
if [ "$relations" = "入力ファイル 1 ファイル名 0..n" ]; then
  echo "ER 図の関連: ok（$relations）"
else
  echo "ER 図の関連: failed（$relations）"
  exit 1
fi
