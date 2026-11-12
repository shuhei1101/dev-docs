"""project-index の端末の設定の API と、追加する配信元の設定のファイルに読み取りだけでつながるかを確かめる。"""

import json
import sys
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8786/settings/sources"
CONFIGS = {
    "dev-docs": Path("/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/develop/project-index.yaml"),
    "knowledge": Path("/mnt/c/Users/shuhe/repo/knowledge/.claude/worktrees/develop/dev-docs.yaml"),
}

failed = False
try:
    with urllib.request.urlopen(API, timeout=10) as response:
        json.load(response)
    print("project-index の端末の設定の API: ok")
except Exception as error:  # noqa: BLE001
    print("project-index の端末の設定の API: failed")
    print(f"GET {API}: {error}", file=sys.stderr)
    failed = True
for source_id, config in CONFIGS.items():
    if config.is_file():
        print(f"{source_id} の設定のファイル: ok")
    else:
        print(f"{source_id} の設定のファイル: failed")
        print(f"{config} がありません", file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
