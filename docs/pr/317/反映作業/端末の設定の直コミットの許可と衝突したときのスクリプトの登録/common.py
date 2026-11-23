"""端末の設定の直コミットの許可と衝突したときのスクリプトの登録で、各スクリプトが共有する値と処理。"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True

# 書き換える project-index の端末の設定のファイル
SETTINGS = Path.home() / ".config/project-index/settings.yaml"
# project-index の端末の設定の API
API = "http://127.0.0.1:8786"
# 直コミットを許可し、衝突したときのスクリプトを登録する配信元
TARGETS = ["dev-docs", "knowledge", "knowledge-memes", "aituber-assets"]
# 衝突したときのスクリプト（dev-docs の稼働しているブランチのワークツリー）
SCRIPT = "/home/shuhei2441/repo/dev-docs/.claude/worktrees/develop/scripts/project-index-on-conflict.sh"
COMMAND = ["bash", SCRIPT]
# 一時的な通信エラー（再読み込みの間の接続の失敗・5xx）の再試行の回数と間隔
RETRIES = 3
RETRY_INTERVAL_SEC = 2
# 端末の設定の API の 1 回の要求の上限（project-index の再読み込みを待つ）
REQUEST_TIMEOUT_SEC = 60


def load_yaml(path: Path) -> object:
    """YAML のファイルを読み込む。"""
    import yaml

    return load_yaml_text(path.read_text(encoding="utf-8"))


def load_yaml_text(text: str) -> object:
    """YAML の文字列を読み込む。"""
    import yaml

    return yaml.safe_load(text)


def request(method: str, path: str, body: object | None = None) -> tuple[int, object]:
    """端末の設定の API を呼び、状態コードと JSON の本文を返却する。"""
    data = None if body is None else json.dumps(body).encode()
    last: Exception | None = None
    for _ in range(RETRIES):
        req = urllib.request.Request(
            API + path, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as res:
                return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as error:
            # 4xx: 再試行せずに状態コードを返却する
            if error.code < 500:
                return error.code, json.loads(error.read() or b"null")
            last = error
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
        time.sleep(RETRY_INTERVAL_SEC)
    raise RuntimeError(f"{method} {path}: {last}")


def source_rows(settings: dict) -> dict[str, dict]:
    """端末の設定の `sources[]` を配信元の ID ごとにする。"""
    return {row.get("id"): row for row in settings.get("sources", [])}


def allowed_kinds(row: dict) -> list[str] | None:
    """配信元の設定の `direct_commit.kinds` の種類の ID を返却する。`direct_commit` が無ければ `None`。"""
    configs = row["config"] if isinstance(row["config"], list) else [row["config"]]
    kinds: list[str] = []
    found = False
    for config in configs:
        direct = (load_yaml(Path(config)) or {}).get("direct_commit")
        if not direct:
            continue
        found = True
        for kind in direct.get("kinds", []):
            # 種類は文字列か `{id, body}` のどちらかで記載されている
            kind_id = kind["id"] if isinstance(kind, dict) else kind
            if kind_id not in kinds:
                kinds.append(kind_id)
    return kinds if found else None
