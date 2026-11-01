from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Locator, Page, expect

GITHUB_CONFIG = "github:\n  repository: example/sample\n  issue_labels: [review]\n"
GITHUB_PAGE = "<title>new issue</title>"
FIRST_COMMENT = "1 つ目のコメント"
SECOND_COMMENT = "2 つ目のコメント"
TRUNCATED_NOTE = (
    "長さの上限を超えたため、本文の末尾を切り詰めました。全文はクリップボードにコピーしています"
)
LONG_BODY = "あ" * 2000


def _panel(page: Page) -> Locator:
    """コメントのパネルのロケータを返す。"""
    return page.get_by_role("dialog", name=re.compile("^コメント"))


def _first_cell(page: Page, table: int) -> Locator:
    """本文の `table` 番目の表の、最初のセルのロケータを返す。"""
    return page.locator("main table").nth(table).locator("td").first


def _wait_comments_attached(page: Page) -> None:
    """mdmark がコメントの部品を付け、選択の変化を受け始めるまで待つ。"""
    expect(page.locator("#mdmark-comment-hint")).to_be_attached()


def _add_comment(page: Page, target: Locator, body: str) -> None:
    """本文の文字列を選んでコメントを追加する。"""
    _wait_comments_attached(page)
    target.scroll_into_view_if_needed()
    target.select_text()
    page.get_by_role("button", name="コメント", exact=True).click()
    page.get_by_role("dialog", name="コメントを書く").get_by_role("textbox").fill(body)
    page.get_by_role("button", name="コメントを保存").click()


def _read_clipboard(page: Page) -> str:
    """クリップボードの文字列を読む。"""
    return str(page.evaluate("navigator.clipboard.readText()"))


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """本文の文字列にコメントを溜め、2 件をまとめてコピーする（正常系）。"""
    # 準備
    served = serve(make_source("notes", screen_files(), git=False))
    page.goto(served.url("/notes/docs/doc-1"))
    expect(_first_cell(page, 0)).to_be_visible()
    # 実行
    _wait_comments_attached(page)
    _first_cell(page, 0).select_text()
    # 検証（文字列を選ぶと、コメントを追加するボタンが出る）
    expect(page.get_by_role("button", name="コメント", exact=True)).to_be_visible()
    # 実行
    _add_comment(page, _first_cell(page, 0), FIRST_COMMENT)
    _add_comment(page, _first_cell(page, 1), SECOND_COMMENT)
    _panel(page).get_by_role("button", name="選択 2 件をコピー").click()
    # 検証
    expect(page.get_by_role("button", name="コメント 2 件")).to_be_visible()
    expect(_panel(page).get_by_role("button", name="Issue を作成")).to_have_count(0)
    expect(page.get_by_text("選択 2 件をクリップボードにコピーしました。")).to_be_visible()
    marks = page.locator("main .mdmark-comment-mark")
    expect(marks).to_have_count(2)
    expect(marks.nth(0)).to_have_text("a0")
    expect(marks.nth(1)).to_have_text("s0")
    copied = _read_clipboard(page)
    assert copied.index(FIRST_COMMENT) < copied.index(SECOND_COMMENT)
    assert "### 文書 1 › 項目" in copied
    assert "### 文書 1 › まとめ" in copied
    assert "docs/doc-1" in copied
    assert "> a0" in copied
    assert "> s0" in copied


def test_normal_when_comment_edited(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """コメントのパネルで 2 件目へ移り、修正と削除をする（正常系）。"""
    # 準備
    served = serve(make_source("notes", screen_files(), git=False))
    page.goto(served.url("/notes/docs/doc-1"))
    expect(_first_cell(page, 0)).to_be_visible()
    _add_comment(page, _first_cell(page, 0), FIRST_COMMENT)
    _add_comment(page, _first_cell(page, 1), SECOND_COMMENT)
    items = _panel(page).get_by_role("listitem")
    # 実行
    page.evaluate("window.scrollTo(0, 0)")
    _panel(page).get_by_role("button", name="文書 1 › まとめ").click()
    # 検証（2 件目の箇所が画面に入る）
    expect(_first_cell(page, 1)).to_be_in_viewport()
    # 実行
    items.nth(1).get_by_role("button", name="修正").click()
    _panel(page).get_by_role("textbox", name="コメント").fill("書き換えたコメント")
    _panel(page).get_by_role("button", name="保存", exact=True).click()
    items.nth(0).get_by_role("button", name="削除").click()
    # 検証
    expect(items).to_have_count(1)
    expect(items.first).to_contain_text("書き換えたコメント")
    expect(page.get_by_role("button", name="コメント 1 件")).to_be_visible()


def test_normal_when_issue_created(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """選んだコメントを載せた Issue の作成画面を別のタブで開く（正常系）。"""
    # 準備
    page.context.route(
        "https://github.com/**",
        lambda route: route.fulfill(status=200, content_type="text/html", body=GITHUB_PAGE),
    )
    served = serve(make_source("sample", screen_files(config_extra=GITHUB_CONFIG)))
    page.goto(served.url("/sample/docs/doc-1"))
    expect(_first_cell(page, 0)).to_be_visible()
    _add_comment(page, _first_cell(page, 0), FIRST_COMMENT)
    # 実行
    with page.expect_popup() as opened:
        _panel(page).get_by_role("button", name="Issue を作成").click()
    popup = opened.value
    popup.wait_for_load_state()
    # 検証
    url = urlsplit(popup.url)
    query = parse_qs(url.query)
    assert (
        f"{url.scheme}://{url.netloc}{url.path}" == "https://github.com/example/sample/issues/new"
    )
    assert query["labels"] == ["review"]
    assert "title" not in query
    assert FIRST_COMMENT in query["body"][0]
    assert "docs/doc-1" in query["body"][0]
    expect(page).to_have_url(re.compile("/sample/docs/doc-1"))


def test_normal_when_issue_body_truncated(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """Issue の本文が長いと、URL の上限に収まるまで末尾を切り詰め、全文をクリップボードに残す（正常系）。"""
    # 準備
    page.context.route(
        "https://github.com/**",
        lambda route: route.fulfill(status=200, content_type="text/html", body=GITHUB_PAGE),
    )
    served = serve(make_source("sample", screen_files(config_extra=GITHUB_CONFIG)))
    page.goto(served.url("/sample/docs/doc-1"))
    expect(_first_cell(page, 0)).to_be_visible()
    _add_comment(page, _first_cell(page, 0), LONG_BODY)
    # 実行
    with page.expect_popup() as opened:
        _panel(page).get_by_role("button", name="Issue を作成").click()
    popup = opened.value
    popup.wait_for_load_state()
    # 検証
    body = parse_qs(urlsplit(popup.url).query)["body"][0]
    clipboard = _read_clipboard(page)
    assert len(popup.url) <= 7200
    assert body.startswith("### 文書 1 › 項目")
    assert TRUNCATED_NOTE in body
    assert LONG_BODY in clipboard
    assert LONG_BODY not in body
