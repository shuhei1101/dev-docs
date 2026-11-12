"""project-index の端末の設定の sources[] から、実行で追加した配信元の行だけを削除する。"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8786/settings/sources"
# 実行.py が追加した行の id の記録
STATE = Path("~/.local/state/dev-docs/反映作業-pr171-追加した配信元.json").expanduser()

if not STATE.is_file():
    print("配信元の行の削除: skipped")
    sys.exit(0)
added = set(json.loads(STATE.read_text(encoding="utf-8")))
with urllib.request.urlopen(API, timeout=10) as response:
    view = json.load(response)
# 応答は camelCase、PUT の本文は端末の設定の行のキー名
rows = [
    {
        "id": row["id"],
        "config": row["config"],
        "enabled": row["enabled"],
        "scope": row["scope"],
        "outside_read": row["outsideRead"],
    }
    for row in view["sources"]
    if row.get("id") not in added
]
if len(rows) == len(view["sources"]):
    print("配信元の行の削除: skipped")
    STATE.unlink()
    sys.exit(0)
req = urllib.request.Request(
    API, data=json.dumps({"sources": rows}).encode(), method="PUT", headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=60):
        pass
except urllib.error.HTTPError as error:
    print("配信元の行の削除: failed")
    print(f"PUT {API}: {error.code} {error.read().decode()}", file=sys.stderr)
    sys.exit(1)
STATE.unlink()
print(f"配信元の行の削除（{', '.join(sorted(added))}）: changed")
