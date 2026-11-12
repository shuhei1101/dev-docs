"""配信元 dev-docs が配信され、判定フローチャートが検索で見つかるかを読むだけで確かめる。"""

import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8786"


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.load(response)


failed = False
statuses = {row.get("id"): row["status"] for row in get("/settings/sources")["sources"]}
for source_id in ("dev-docs", "knowledge"):
    status = statuses.get(source_id)
    print(f"配信元 {source_id} の状態（{status}）: {'ok' if status == 'serving' else 'failed'}")
    failed |= status != "serving"
if not failed:
    query = urllib.parse.quote("判定")
    result = json.dumps(get(f"/sources/dev-docs/search?q={query}"), ensure_ascii=False)
    for doc_id in ("flowchart-new-or-modify", "flowchart-documents-row"):
        found = doc_id in result
        print(f"検索で {doc_id} が見つかる: {'ok' if found else 'failed'}")
        failed |= not found
sys.exit(1 if failed else 0)
