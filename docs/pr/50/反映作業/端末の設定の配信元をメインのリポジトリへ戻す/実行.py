"""端末の設定の 4 つの配信元の config をメインのリポジトリの dev-docs.yaml へ書き換え、管理の MCP の reload で読み直す。

`--dry-run` を付けると計画まで進んで止まる。
"""

import difflib
import os
import shutil
import sys
import tempfile

from mcp_client import (
    ADMIN_MCP_URL,
    BACKUP,
    REPLACEMENTS,
    SETTINGS,
    call_tool,
    config_at_default_ref,
)


def missing_targets() -> list[str]:
    """書き換え先の dev-docs.yaml のうち、`default_ref` の commit に無いものを返す。"""
    return [new for _, new in REPLACEMENTS if not config_at_default_ref(new)]


def plan(current: str) -> str:
    """書き換えた後の端末の設定の中身を返す。"""
    planned = current
    for old, new in REPLACEMENTS:
        planned = planned.replace(f"config: {old}\n", f"config: {new}\n")
    return planned


def validate(planned: str) -> bool:
    """4 つの書き換え先が 1 回ずつ現れ、書き換え前のパスが残っていないか。"""
    return all(
        planned.count(f"config: {new}\n") == 1 and old not in planned for old, new in REPLACEMENTS
    )


def apply(planned: str) -> None:
    """退避してから一時ファイル経由で端末の設定を置き換える。"""
    shutil.copy2(SETTINGS, BACKUP)
    with tempfile.NamedTemporaryFile(
        "w", dir=SETTINGS.parent, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(planned)
    shutil.copymode(SETTINGS, tmp.name)
    os.replace(tmp.name, SETTINGS)


def main() -> int:
    """前提確認 → 計画 → 適用の順に進め、手順ごとに結果の行を出す。"""
    dry_run = "--dry-run" in sys.argv[1:]

    # 前提確認
    if not SETTINGS.is_file():
        print("前提確認: failed (端末の設定がありません)")
        return 1
    missing = missing_targets()
    if missing:
        # 書き換え先が無いまま書き換えると配信元が読めなくなるため、適用はしない。dry-run は差分まで出す
        print(f"前提確認: failed (default_ref に無い: {', '.join(missing)})")
        if not dry_run:
            return 1
    else:
        print("前提確認: ok")

    # 計画（--dry-run もここを通る）
    current = SETTINGS.read_text(encoding="utf-8")
    planned = plan(current)
    if planned == current:
        # 既にメインのリポジトリを指している
        print("端末の設定の書き換え: skipped")
        return 0
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        planned.splitlines(keepends=True),
        fromfile=str(SETTINGS),
        tofile=str(SETTINGS),
    )
    sys.stdout.writelines(diff)
    if dry_run:
        print("端末の設定の書き換え: changed")
        print("読み直し: changed")
        return 1 if missing else 0

    # 適用（検証 → 退避 → 置き換え → 読み直し）
    if not validate(planned):
        print("検証: failed")
        return 1
    print("検証: ok")
    apply(planned)
    print("端末の設定の書き換え: changed")
    try:
        call_tool(ADMIN_MCP_URL, "reload", {})
    except (OSError, RuntimeError) as error:
        print(f"読み直し: failed ({error})")
        return 1
    print("読み直し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
