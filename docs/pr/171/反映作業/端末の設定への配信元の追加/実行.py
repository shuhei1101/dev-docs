"""project-index の端末の設定の sources[] に、配信元 dev-docs と knowledge の行を追加する。"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8786/settings/sources"
# 追加した行の id の記録（切り戻しは、ここに記録した行だけを削除する）
STATE = Path("~/.local/state/dev-docs/反映作業-pr171-追加した配信元.json").expanduser()
ROWS = [
    {
        "id": "dev-docs",
        "config": ["/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/project-index.yaml"],
        "scope": {
            "read": ["/mnt/c/Users/shuhe/repo/dev-docs/**"],
            "write": ["/mnt/c/Users/shuhe/repo/dev-docs"],
        },
    },
    {
        "id": "knowledge",
        "config": ["/mnt/c/Users/shuhe/repo/knowledge/.claude/worktrees/develop/dev-docs.yaml"],
        "scope": {
            "read": ["/mnt/c/Users/shuhe/repo/knowledge/**"],
            "write": ["/mnt/c/Users/shuhe/repo/knowledge"],
        },
    },
]


def request(method: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


# 前提確認
if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--dry-run"):
    print("前提確認: failed")
    print(f"引数 {sys.argv[1:]} は受け付けません", file=sys.stderr)
    sys.exit(1)
dry_run = len(sys.argv) == 2
try:
    _, view = request("GET")
except Exception as error:  # noqa: BLE001
    print("前提確認: failed")
    print(f"GET {API}: {error}", file=sys.stderr)
    sys.exit(1)
missing = [row["config"][0] for row in ROWS if not Path(row["config"][0]).is_file()]
if missing:
    print("前提確認: failed")
    print(f"設定のファイルがありません: {missing}", file=sys.stderr)
    sys.exit(1)
print("前提確認: ok")
print(f"端末の設定: {view['settingsPath']}")

# 計画（--dry-run もここを通る）
existing = {row.get("id"): row for row in view["sources"]}
failed = False
for row in ROWS:
    step = f"配信元 {row['id']} の行の追加"
    if row["id"] in existing:
        same = existing[row["id"]]["config"] == row["config"]
        print(f"{step}: {'skipped' if same else 'failed'}")
        if not same:
            print(f"同じ id の別の行があります: {existing[row['id']]['config']}", file=sys.stderr)
            failed = True
        continue
    print(f"+ {json.dumps(row, ensure_ascii=False)}")
    if dry_run:
        print(f"{step}: changed")
        continue
    # 適用（サーバーが端末の設定を書き換えて読み直す）
    status, body = request("POST", {"source": row})
    if status == 201 and body.get("result") == "added":
        added = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else []
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(sorted({*added, row["id"]})), encoding="utf-8")
        print(f"{step}: changed")
    else:
        print(f"{step}: failed")
        print(f"POST {API}: {status} {json.dumps(body, ensure_ascii=False)}", file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
