#!/bin/sh
set -u
DEVELOP=/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop
SETTINGS="$HOME/.config/dev-docs/settings.yaml"
PI_SETTINGS="$HOME/.config/project-index/settings.yaml"
rc=0
ADDRESS=http://127.0.0.1:8786
FIXED=src/dev_docs/features/migrate/service.py
# 稼働中の project-index のサーバーが PUT /settings/sources の expectedVersion を受け付けるか。
# 今の内容のバージョンと一致しない expectedVersion を付けて PUT し、409（書き込まない）なら受け付ける。
# 受け付けない古いバージョンは 400（expectedVersion: Extra inputs are not permitted）を返す。
# 本文の sources は GET で取った今の行にし、照合せずに保存するサーバーに当たっても中身を変えない。
probe_expected_version() {
  if ! probe_body=$(curl -s -m 10 "$ADDRESS/settings/sources" | python3 -B -c "import json, re, sys
rows = []
for row in json.load(sys.stdin)['sources']:
    sent = {key: row[key] for key in ('config', 'enabled', 'scope') if key in row}
    if isinstance(row.get('id'), str) and not re.fullmatch(r'sources\[\d+\]', row['id']):
        sent['id'] = row['id']
    if 'outsideRead' in row:
        sent['outside_read'] = row['outsideRead']
    rows.append(sent)
print(json.dumps({'sources': rows, 'expectedVersion': 'dev-docs-pr212-probe'}))" 2>&1); then
    echo "project-index のサーバーの expectedVersion: failed（GET /settings/sources の今の行を読めない）"
    echo "$probe_body"
    return 1
  fi
  probe_out=$(mktemp)
  probe_code=$(curl -s -m 30 -o "$probe_out" -w '%{http_code}' -X PUT "$ADDRESS/settings/sources" \
    -H 'Content-Type: application/json' -d "$probe_body" || true)
  probe_body=$(cat "$probe_out"); rm -f "$probe_out"
  if [ "$probe_code" = "409" ]; then
    echo "project-index のサーバーの expectedVersion: ok"
    return 0
  fi
  echo "project-index のサーバーの expectedVersion: failed（PUT /settings/sources が $probe_code。expectedVersion を受け付けるバージョン（project-index の develop の 7177d39 以降）で起動し直してから依頼元へ返す）"
  echo "$probe_body"
  return 1
}
if out=$(cd "$DEVELOP" && uv run dev-docs migrate --help 2>&1); then echo "dev-docs の develop: ok"; else echo "dev-docs の develop: failed"; echo "$out"; rc=1; fi
if [ -r "$SETTINGS" ]; then echo "dev-docs の端末の設定: ok"; else echo "dev-docs の端末の設定: failed"; rc=1; fi
if [ -r "$PI_SETTINGS" ]; then echo "project-index の端末の設定: ok"; else echo "project-index の端末の設定: failed"; rc=1; fi
code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8786/settings/sources || true)
if [ "$code" = "200" ]; then echo "project-index の端末の設定の API: ok"; else echo "project-index の端末の設定の API: failed"; echo "GET /settings/sources: $code"; rc=1; fi
if [ "$rc" = 0 ]; then probe_expected_version || rc=1; fi
if grep -q '"enabled", "scope", "outside_read"' "$DEVELOP/$FIXED"; then echo "dev-docs の develop の送信するキー: ok"; else echo "dev-docs の develop の送信するキー: failed（$FIXED が outside_read で送信しない。作業 PR #212 のマージの前）"; rc=1; fi
exit $rc
