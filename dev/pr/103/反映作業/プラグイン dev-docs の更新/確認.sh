#!/bin/sh
set -u

rc=0
for dir in /home/shuhei2441/.claude /home/shuhei2441/.claude-*; do
  file="$dir/plugins/installed_plugins.json"
  [ -f "$file" ] && grep -q '"dev-docs@dev-docs"' "$file" || continue
  for hook in $(python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
for item in data.get('plugins', {}).get('dev-docs@dev-docs', []):
    print(item['installPath'] + '/hooks/session_start.py')
" "$file"); do
    if grep -q '/_admin/session-start' "$hook" && ! grep -q '/_admin/session-context' "$hook" && ! grep -q 'fetch_context' "$hook"; then
      echo "$dir（$hook）: ok"
    else
      echo "$dir（$hook）: failed（前のバージョンのフック）"
      rc=1
    fi
  done
done
exit $rc
