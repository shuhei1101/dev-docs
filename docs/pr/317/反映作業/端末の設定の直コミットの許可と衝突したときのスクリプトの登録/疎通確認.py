"""端末の設定のファイル・端末の設定の API・衝突したときのスクリプトに、読み取りだけでつながるかを確認する。"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402


def main() -> int:
    """対象ごとに 1 行の結果を出し、`failed` があれば 1 を返却する。"""
    failed = False
    # 端末の設定のファイル
    if common.SETTINGS.is_file():
        print("端末の設定のファイル: ok")
    else:
        print("端末の設定のファイル: failed")
        print(f"{common.SETTINGS} がありません", file=sys.stderr)
        failed = True
    # 端末の設定の API
    try:
        status, _ = common.request("GET", "/settings/sources")
        print("端末の設定の API: " + ("ok" if status == 200 else "failed"))
        failed = failed or status != 200
    except RuntimeError as error:
        print("端末の設定の API: failed")
        print(error, file=sys.stderr)
        failed = True
    # 衝突したときのスクリプト（マージの後に稼働しているブランチへ入る）
    if Path(common.SCRIPT).is_file():
        print("衝突したときのスクリプト: ok")
    else:
        print("衝突したときのスクリプト: failed")
        print(f"{common.SCRIPT} がありません", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
