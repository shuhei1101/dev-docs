"""対象の配信元の行に、書き込みの API から直コミットできる種類と衝突したときのスクリプトを登録する。

`on_conflict` は端末の設定の API が受け付けないため、端末の設定のファイルへ記載してから、
1 行の変更（PATCH）で `write_api_kinds` を送信して、その行の配信元を再読み込みさせる。
"""

import difflib
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

# 端末の設定のファイルの先頭のコメント（YAML の書き出しで消えるため戻す）
HEADER_PREFIX = "#"


def fail(step: str, detail: str) -> int:
    """失敗の行と詳細を出して 1 を返却する。"""
    print(f"{step}: failed")
    print(detail, file=sys.stderr)
    return 1


def dump(settings: dict, header: list[str]) -> str:
    """端末の設定を YAML の文字列にする（キーの順を保ち、先頭のコメントを戻す）。"""
    import yaml

    body = yaml.safe_dump(settings, allow_unicode=True, sort_keys=False)
    return "".join(line + "\n" for line in header) + body


def main(argv: list[str]) -> int:
    """前提確認 → 計画 → 適用の順に進める。"""
    # 前提確認: 引数は無しか --dry-run だけ
    if len(argv) > 1 or (len(argv) == 1 and argv[0] != "--dry-run"):
        return fail("前提確認", f"受け付けない引数です: {argv}")
    dry_run = argv == ["--dry-run"]
    if not common.SETTINGS.is_file():
        return fail("前提確認", f"{common.SETTINGS} がありません")
    if not Path(common.SCRIPT).is_file():
        return fail("前提確認", f"{common.SCRIPT} がありません")
    original = common.SETTINGS.read_text(encoding="utf-8")
    settings = common.load_yaml(common.SETTINGS)
    header = [line for line in original.splitlines() if line.startswith(HEADER_PREFIX)][:1]
    rows = common.source_rows(settings)
    missing = [target for target in common.TARGETS if target not in rows]
    if missing:
        return fail("前提確認", f"端末の設定に行がありません: {missing}")
    kinds_by_target: dict[str, list[str]] = {}
    for target in common.TARGETS:
        kinds = common.allowed_kinds(rows[target])
        # 配信元の設定に direct_commit が無い: 許可する種類を決められない
        if not kinds:
            return fail("前提確認", f"{target} の配信元の設定に direct_commit.kinds がありません")
        kinds_by_target[target] = kinds
    print("前提確認: ok")

    # 計画: ファイルへ記載する on_conflict と、送信する write_api_kinds
    file_changed = False
    patches: dict[str, list[str]] = {}
    for target in common.TARGETS:
        direct = rows[target].setdefault("direct_commit", {})
        if direct.get("on_conflict", {}).get("command") != common.COMMAND:
            direct["on_conflict"] = {"command": common.COMMAND}
            file_changed = True
        if direct.get("write_api_kinds") != kinds_by_target[target]:
            patches[target] = kinds_by_target[target]
    if not file_changed and not patches:
        print("衝突したときのスクリプトの登録: skipped")
        print("直コミットできる種類の登録: skipped")
        return 0
    # write_api_kinds は PATCH で送信するため、ファイルには記載しない
    planned = common.load_yaml(common.SETTINGS)
    for target in common.TARGETS:
        planned_row = common.source_rows(planned)[target]
        planned_row.setdefault("direct_commit", {})["on_conflict"] = {"command": common.COMMAND}
    new_text = dump(planned, header)
    sys.stdout.writelines(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(common.SETTINGS),
            tofile=str(common.SETTINGS),
        )
    )
    for target, kinds in patches.items():
        print(f"{target} の write_api_kinds: {kinds}")
    if dry_run:
        print("衝突したときのスクリプトの登録: " + ("changed" if file_changed else "skipped"))
        print("直コミットできる種類の登録: " + ("changed" if patches else "skipped"))
        return 0

    # 適用: 検証 → 退避 → 置き換え
    if file_changed:
        checked = common.source_rows(common.load_yaml_text(new_text))
        if any(checked[t]["direct_commit"]["on_conflict"]["command"] != common.COMMAND for t in common.TARGETS):
            return fail("検証", "書き出した端末の設定に on_conflict がありません")
        print("検証: ok")
        backup = common.SETTINGS.with_name(f"settings.yaml.bak-{datetime.now():%Y%m%d-%H%M%S}")
        backup.write_text(original, encoding="utf-8")
        print(f"退避: changed（{backup}）")
        common.SETTINGS.write_text(new_text, encoding="utf-8")
        print("衝突したときのスクリプトの登録: changed")
    else:
        print("衝突したときのスクリプトの登録: skipped")
    # 1 行の変更で write_api_kinds を送信し、その行の配信元を再読み込みさせる
    # （on_conflict を記載した行は、write_api_kinds が同じでも再読み込みさせる）
    targets = common.TARGETS if file_changed else list(patches)
    status, body = common.request("GET", "/settings/sources")
    if status != 200:
        return fail("直コミットできる種類の登録", f"GET /settings/sources: {status} {body}")
    version = body["version"]
    for target in targets:
        status, body = common.request(
            "PATCH",
            f"/settings/sources/{target}",
            {"expectedVersion": version, "source": {"direct_commit": {"write_api_kinds": kinds_by_target[target]}}},
        )
        if status != 200:
            return fail("直コミットできる種類の登録", f"PATCH /settings/sources/{target}: {status} {body}")
        version = body["version"]
    print("直コミットできる種類の登録: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
