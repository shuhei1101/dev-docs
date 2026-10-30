from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

NOT_FOUND_TITLE = "見つかりません | dev-docs"


def _rows(settings: Any) -> dict[str, Any]:
    """端末の設定の `sources` を、配信元の ID から行を引く辞書にする。"""
    return {row["id"]: row for row in settings["sources"]}


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    snapshot: Callable[[Path], dict[str, bytes]],
    page: Page,
) -> None:
    """設定画面で配信元を削除し、再起動せずに配信から外す（正常系）。"""
    # 準備
    sample = make_source("sample")
    extra = make_source("extra")
    extra_before = snapshot(extra.folder)
    served = serve(sample, extra)
    sample_row = _rows(load_yaml_file(served.settings))["sample"]
    page.goto(served.url("/_settings"))
    dialog = page.get_by_role("alertdialog")
    # 実行
    page.get_by_role("button", name="extra を削除").click()
    # 検証（確認のダイアログに、フォルダと文書は削除しないことが出る）
    expect(dialog).to_contain_text(f"フォルダ {extra.folder} と文書は削除しません。")
    # 実行
    dialog.get_by_role("button", name="削除", exact=True).click()
    # 検証（保存が終わってダイアログが閉じてから読む）
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("button", name="extra を削除")).to_have_count(0)
    after = _rows(load_yaml_file(served.settings))
    assert list(after) == ["sample"]
    # 設定ファイルが 1 つの行は、保存で文字列として書かれる
    assert after["sample"] == {**sample_row, "config": str(sample.config[0])}
    assert snapshot(extra.folder) == extra_before
    page.goto(served.url("/extra"))
    expect(page).to_have_title(NOT_FOUND_TITLE)
    page.goto(served.url("/sample"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text("文書 1")


def test_normal_when_source_disabled(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    load_yaml_file: Callable[[Path], Any],
    page: Page,
) -> None:
    """設定画面で配信するを外して保存すると、その配信元だけが配信から外れる（正常系）。"""
    # 準備
    served = serve(make_source("sample"), make_source("extra"))
    page.goto(served.url("/_settings"))
    dialog = page.get_by_role("dialog")
    # 実行
    page.get_by_role("button", name="extra を編集").click()
    dialog.get_by_role("switch", name="配信する").click()
    dialog.get_by_role("button", name="保存", exact=True).click()
    # 検証
    expect(dialog).to_have_count(0)
    expect(page.get_by_text("無効", exact=True)).to_be_visible()
    rows = _rows(load_yaml_file(served.settings))
    assert rows["extra"]["enabled"] is False
    assert "enabled" not in rows["sample"]
    page.goto(served.url("/extra"))
    expect(page).to_have_title(NOT_FOUND_TITLE)
    page.goto(served.url("/sample"))
    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_have_text("文書 1")
