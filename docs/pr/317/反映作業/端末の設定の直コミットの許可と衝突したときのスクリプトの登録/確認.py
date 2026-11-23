"""対象の配信元の行が、直コミットできる種類と衝突したときのスクリプトを持つかを観測する。"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402


def main() -> int:
    """対象ごとに観測した値を出し、どれかが合わなければ 1 を返却する。"""
    status, body = common.request("GET", "/settings/sources")
    if status != 200:
        print("端末の設定の API: failed")
        print(f"GET /settings/sources: {status} {body}", file=sys.stderr)
        return 1
    api_rows = {row.get("id"): row for row in body["sources"]}
    file_rows = common.source_rows(common.load_yaml(common.SETTINGS))
    failed = False
    for target in common.TARGETS:
        expected = common.allowed_kinds(file_rows[target]) or []
        actual = ((api_rows.get(target) or {}).get("directCommit") or {}).get("writeApiKinds")
        ok = actual == expected
        print(f"{target} の writeApiKinds: {'ok' if ok else 'failed'}（{actual}）")
        failed = failed or not ok
        # on_conflict は端末の設定の API が返却しないため、ファイルで観測する
        command = ((file_rows[target].get("direct_commit") or {}).get("on_conflict") or {}).get("command")
        ok = command == common.COMMAND
        print(f"{target} の on_conflict.command: {'ok' if ok else 'failed'}（{command}）")
        failed = failed or not ok
        # 配信を続けているか
        served = (api_rows.get(target) or {}).get("status")
        ok = served == "serving"
        print(f"{target} の状態: {'ok' if ok else 'failed'}（{served}）")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
