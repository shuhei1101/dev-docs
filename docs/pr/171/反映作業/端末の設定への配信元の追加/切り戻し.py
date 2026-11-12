"""project-index の端末の設定の sources[] から、追加した配信元 dev-docs と knowledge の行を削除する。"""

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8786/settings/sources"
IDS = ("dev-docs", "knowledge")

with urllib.request.urlopen(API, timeout=10) as response:
    view = json.load(response)
rows = [
    {key: row[key] for key in ("id", "config", "enabled", "scope", "outside_read")}
    for row in view["sources"]
    if row.get("id") not in IDS
]
if len(rows) == len(view["sources"]):
    print("配信元の行の削除: skipped")
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
print("配信元の行の削除: changed")
