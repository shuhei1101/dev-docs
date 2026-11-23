"""実行で退避した最新の端末の設定のファイルへ戻し、対象の行の write_api_kinds を戻して再読み込みさせる。"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402


def main() -> int:
    """退避したファイルを戻し、1 行の変更で退避時の write_api_kinds を送信する。"""
    backups = sorted(common.SETTINGS.parent.glob("settings.yaml.bak-*"))
    # 退避したファイルが無い: 戻す元が無いので止める
    if not backups:
        print("退避したファイル: failed")
        print(f"{common.SETTINGS.parent} に settings.yaml.bak-* がありません", file=sys.stderr)
        return 1
    backup = backups[-1]
    print(f"退避したファイル: ok（{backup}）")
    text = backup.read_text(encoding="utf-8")
    common.SETTINGS.write_text(text, encoding="utf-8")
    print("端末の設定のファイルの戻し: changed")
    rows = common.source_rows(common.load_yaml_text(text))
    status, body = common.request("GET", "/settings/sources")
    if status != 200:
        print("直コミットできる種類の戻し: failed")
        print(f"GET /settings/sources: {status} {body}", file=sys.stderr)
        return 1
    version = body["version"]
    for target in common.TARGETS:
        kinds = (rows[target].get("direct_commit") or {}).get("write_api_kinds", [])
        status, body = common.request(
            "PATCH",
            f"/settings/sources/{target}",
            {"expectedVersion": version, "source": {"direct_commit": {"write_api_kinds": kinds}}},
        )
        if status != 200:
            print("直コミットできる種類の戻し: failed")
            print(f"PATCH /settings/sources/{target}: {status} {body}", file=sys.stderr)
            return 1
        version = body["version"]
    print("直コミットできる種類の戻し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
