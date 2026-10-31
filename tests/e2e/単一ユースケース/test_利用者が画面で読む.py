from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, expect

FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
MEMO_ROW = "  - id: memo\n    title: メモ\n    paths: [notes/*.yaml]\n    schema: schemas/sample.schema.yaml\n"
CUSTOM_EXTRA = (
    "  - id: custom\n"
    "    paths: [custom/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    converter: md\n"
    "  - id: guide\n"
    "    paths: [guide/files.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
    "converters:\n"
    "  - id: md\n"
    "    run: [python3, scripts/convert.py]\n"
)
CONVERT_SCRIPT = (
    "import sys\n"
    "text = sys.stdin.read()\n"
    "name = next(line.split(':', 1)[1].strip() for line in text.splitlines()"
    " if line.startswith('name:'))\n"
    "print('# 変換のタイトル')\n"
    "print()\n"
    "print(f'## カスタムの見出し {name}')\n"
)
COLUMNS_EXTRA = (
    "  - id: guide\n"
    "    paths: [guide/files.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)
COLUMNS_TABLE = (
    "# 文書 5\n\n"
    "<!-- table: data +columns -->\n"
    "| キー | 名称 | 備考 |\n"
    "| --- | --- | --- |\n"
    "| k1 | 名称 1 | 備考 1 |\n"
    "<!-- /table -->\n"
)
NOTES_EXTRA = (
    "  - id: notes\n"
    "    paths: [notes/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
    "nav:\n"
    "  tabs:\n"
    "    - title: メモ\n"
    "      items:\n"
    "        - auto:\n"
    "            document: notes\n"
)
SLEEP_SCRIPT = "import time\ntime.sleep(60)\n"
SMALL_ROWS = [{"key": "k1", "label": "名称 1", "notes": "備考 1"}]


def _custom_files(
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    script: str,
) -> dict[str, str]:
    """`converters[]` のスクリプトと埋め込みのマーカーを持つ配信元のファイル一式を返す。"""
    return sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(CUSTOM_EXTRA, name="custom"),
            "scripts/convert.py": script,
            "custom/c-1.yaml": "id: c-1\nname: カスタム 1\n",
            "guide/files.yaml": "files:\n  - path: intro.md\n",
            "guide/intro.md": "# 案内\n\n<!-- embed: data/rows.yaml#rows -->\n",
            "data/rows.yaml": "rows:\n  - {colA: 値A, colB: 値B}\n",
        }
    )


def _heading(page: Page, level: int = 1) -> Locator:
    """本文の領域の見出しのロケータを返す。"""
    return page.get_by_role("main").get_by_role("heading", level=level)


def _side_link(page: Page, title: str) -> Locator:
    """サイドバーの、文書の名前を含むリンクのロケータを返す。"""
    return (
        page.get_by_role("navigation", name="文書の一覧").get_by_role("link").filter(has_text=title)
    )


def _diff_doc(sample_doc_text: Callable[..., str], notes: str) -> str:
    """まとめの表の備考を `notes` にした文書 1 の YAML を作る。"""
    summary = [{"key": "s1", "label": "名称", "notes": notes}]
    return sample_doc_text("doc-1", "文書 1", items=SMALL_ROWS, summary=summary)


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """文書の画面で、タブ・本文・目次を出し、文書 2 へ移る（正常系）。"""
    # 準備
    served = serve(make_source("sample", screen_files()))
    tabs = page.get_by_role("navigation", name="文書の種類")
    sidebar = page.get_by_role("navigation", name="文書の一覧")
    toc = page.get_by_role("navigation", name="目次")
    # 実行
    page.goto(served.url("/sample"))
    # 検証
    expect(_heading(page)).to_have_text("文書 1")
    expect(tabs.locator("a, button")).to_have_text(["規約", "補足"])
    expect(tabs.get_by_role("link", name="規約")).to_have_attribute("aria-current", "page")
    expect(_heading(page, 2).filter(has_text="項目")).to_be_visible()
    expect(_heading(page, 2).filter(has_text="まとめ")).to_be_visible()
    expect(page.locator("main table").first.locator("th")).to_have_text(["キー", "名称", "備考"])
    expect(page.locator("main .mdmark")).to_have_count(1)
    expect(toc.get_by_role("link")).to_have_text(["項目", "まとめ"])
    # 本文を下までスクロールしても、種類のタブとサイドバーが画面に残る
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    expect(tabs).to_be_in_viewport()
    expect(sidebar).to_be_in_viewport()
    # サイドバーで文書 2 を選ぶ
    sidebar.get_by_role("link", name="文書 2").click()
    expect(page).to_have_url(re.compile(r"/sample/docs/doc-2$"))
    expect(_heading(page)).to_have_text("文書 2")
    expect(toc.get_by_role("link")).to_have_text(["項目", "まとめ"])
    # 文書 2 の URL を直接開いても同じ
    page.goto(served.url("/sample/docs/doc-2"))
    expect(_heading(page)).to_have_text("文書 2")
    expect(toc.get_by_role("link")).to_have_text(["項目", "まとめ"])


def test_normal_when_nav_missing(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    sample_doc_text: Callable[..., str],
    page: Page,
) -> None:
    """nav が無い配信元は種類ごとにタブを作る（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(MEMO_ROW),
            "notes/n-1.yaml": sample_doc_text("n-1", "メモ 1"),
        }
    )
    served = serve(make_source("plain", files))
    tabs = page.get_by_role("navigation", name="文書の種類")
    sidebar = page.get_by_role("navigation", name="文書の一覧")
    # 実行
    page.goto(served.url("/plain"))
    # 検証
    expect(tabs.locator("a, button")).to_have_text(["sample", "メモ"])
    expect(sidebar.get_by_role("link")).to_have_text(["文書 1", "文書 2"])
    tabs.get_by_role("link", name="メモ").click()
    expect(sidebar.get_by_role("link")).to_have_text(["メモ 1"])


def test_normal_when_ref_switched(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
    page: Page,
) -> None:
    """リビジョンを切り替えると、古い commit の文書を出す（正常系）。"""
    # 準備
    source = make_source("sample", screen_files())
    old = run_git(source.folder, "rev-parse", "--short=7", "HEAD").strip()
    renamed = sample_doc_text("doc-1", "新しい名前", items=SMALL_ROWS, summary=SMALL_ROWS)
    commit_all(source.folder, {"docs/doc-1.yaml": renamed}, "docs: 改名")
    served = serve(source)
    ref_button = page.get_by_role("button", name=re.compile("^リビジョンを切り替える"))
    # 実行
    page.goto(served.url("/sample/docs/doc-1"))
    expect(_heading(page)).to_have_text("新しい名前")
    ref_button.click()
    page.get_by_role("menuitem", name=re.compile(old)).click()
    # 検証
    expect(page).to_have_url(re.compile(f"rev={old}"))
    expect(_heading(page)).to_have_text("文書 1")
    expect(ref_button).to_have_attribute("aria-label", f"リビジョンを切り替える。今は {old}")
    page.reload()
    expect(_heading(page)).to_have_text("文書 1")
    _side_link(page, "文書 2").click()
    expect(page).to_have_url(re.compile(f"/sample/docs/doc-2\\?rev={old}"))
    expect(_heading(page)).to_have_text("文書 2")


def test_normal_when_diff_shown(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
    page: Page,
) -> None:
    """2 つのリビジョンの差分を、案内とマーカーつきで出し、解除で消す（正常系）。"""
    # 準備
    source = make_source(
        "sample",
        screen_files(
            **{
                "docs/doc-1.yaml": _diff_doc(sample_doc_text, "元の値"),
                "docs/doc-4.yaml": sample_doc_text("doc-4", "文書 4", items=SMALL_ROWS),
            }
        ),
    )
    base = run_git(source.folder, "rev-parse", "--short=7", "HEAD").strip()
    commit_all(
        source.folder,
        {
            "docs/doc-1.yaml": _diff_doc(sample_doc_text, "新しい値"),
            "docs/doc-3.yaml": sample_doc_text("doc-3", "文書 3", items=SMALL_ROWS),
        },
        "docs: 差分",
        delete=("docs/doc-4.yaml",),
    )
    head = run_git(source.folder, "rev-parse", "--short=7", "HEAD").strip()
    served = serve(source)
    banner = page.get_by_role("region", name="差分")
    toc = page.get_by_role("navigation", name="目次")
    # 実行
    page.goto(served.url(f"/sample/docs/doc-1?rev={head}&base={base}"))
    # 検証
    expect(banner.get_by_role("combobox", name="比較元")).to_contain_text(base)
    expect(banner.get_by_role("combobox", name="比較先")).to_contain_text(head)
    expect(_side_link(page, "文書 3").get_by_role("img", name="追加")).to_be_visible()
    expect(_side_link(page, "文書 1").get_by_role("img", name="変更")).to_be_visible()
    expect(_side_link(page, "文書 4").get_by_role("img", name="削除")).to_be_visible()
    expect(_side_link(page, "文書 2").get_by_role("img")).to_have_count(0)
    expect(toc.get_by_role("link").filter(has_text="まとめ")).to_contain_text("変更")
    expect(toc.get_by_role("link").filter(has_text="項目")).not_to_contain_text("変更")
    # URL を開き直しても同じ差分が出る
    page.reload()
    expect(banner).to_be_visible()
    expect(_side_link(page, "文書 3").get_by_role("img", name="追加")).to_be_visible()
    expect(_side_link(page, "文書 1").get_by_role("img", name="変更")).to_be_visible()
    expect(_side_link(page, "文書 4").get_by_role("img", name="削除")).to_be_visible()
    expect(toc.get_by_role("link").filter(has_text="まとめ")).to_contain_text("変更")
    expect(toc.get_by_role("link").filter(has_text="項目")).not_to_contain_text("変更")
    # 強調を解除する
    banner.get_by_role("button", name="差分の強調を解除").click()
    expect(page).not_to_have_url(re.compile("base="))
    expect(banner).to_have_count(0)
    expect(page.get_by_role("navigation", name="文書の一覧").get_by_role("img")).to_have_count(0)
    expect(toc.get_by_text("変更")).to_have_count(0)


def test_normal_when_searched(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """Ctrl+K で検索のダイアログを開き、結果の文書を開く（正常系）。"""
    # 準備
    served = serve(make_source("sample", screen_files()))
    page.goto(served.url("/sample/docs/doc-1"))
    expect(_heading(page)).to_have_text("文書 1")
    dialog = page.get_by_role("dialog", name="文書を検索")
    # 実行
    page.keyboard.press("Control+k")
    expect(dialog).to_be_visible()
    expect(page.get_by_placeholder("文書を検索")).to_be_focused()
    page.get_by_placeholder("文書を検索").fill("パンプキン")
    # 検証
    options = dialog.get_by_role("option")
    expect(options).to_have_count(1)
    expect(options.first).to_contain_text("文書 2")
    expect(options.first.locator("mark")).to_contain_text("パンプキン")
    options.first.click()
    expect(dialog).to_have_count(0)
    expect(_heading(page)).to_have_text("文書 2")


def test_normal_when_column_hidden(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    snapshot: Callable[[Path], dict[str, bytes]],
    page: Page,
) -> None:
    """表の列の表示から 2 列目を外すと、開き直しても隠れたままになる（正常系）。"""
    # 準備
    source = make_source(
        "sample",
        screen_files(
            nav=False,
            config_extra=COLUMNS_EXTRA,
            **{"guide/files.yaml": "files:\n  - path: table.md\n", "guide/table.md": COLUMNS_TABLE},
        ),
    )
    before = snapshot(source.folder)
    served = serve(source)
    page.goto(served.url("/sample/guide/files/guide/table"))
    columns = page.get_by_role("button", name=re.compile("^列の表示")).first
    # 実行
    columns.click()
    page.get_by_role("dialog", name="表示する列").first.get_by_label("名称").uncheck()
    # 検証
    expect(page.locator("main table").first.locator("th:visible")).to_have_text(["キー", "備考"])
    page.reload()
    expect(page.locator("main table").first.locator("th:visible")).to_have_text(["キー", "備考"])
    assert snapshot(source.folder) == before


def test_normal_when_files_index_relative_link(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """管理用の YAML の行の文書の本文の相対リンクを押すと、リンク先の文書を開く（正常系）。"""
    # 準備
    source = make_source(
        "sample",
        screen_files(
            nav=False,
            config_extra=NOTES_EXTRA,
            **{
                "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
                "notes/files.yaml": "files:\n  - path: a.md\n  - path: b.md\n",
                "notes/a.md": "# A\n\n[B](./b.md)\n",
                "notes/b.md": "# B\n\nB の本文。\n",
            },
        ),
    )
    served = serve(source)
    page.goto(served.url("/sample/notes/files/notes/a"))
    expect(_heading(page)).to_have_text("A")
    # 実行
    page.get_by_role("main").get_by_role("link", name="B").click()
    # 検証
    expect(page).to_have_url(re.compile(r"/sample/notes/files/notes/b$"))
    expect(_heading(page)).to_have_text("B")
    expect(page.get_by_role("main")).to_contain_text("B の本文。")
    expect(page.get_by_role("main")).not_to_contain_text("文書が見つかりません")
    current = page.get_by_role("navigation", name="文書の一覧").locator('[aria-current="page"]')
    expect(current).to_have_attribute("href", re.compile(r"/notes/files/notes/b$"))


def test_normal_when_custom_converter(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    page: Page,
) -> None:
    """converters[] のスクリプトの Markdown と、埋め込みのマーカーの表を出す（正常系）。"""
    # 準備
    files = _custom_files(sample_file_set, sample_config_text, CONVERT_SCRIPT)
    served = serve(make_source("custom", files))
    # 実行
    page.goto(served.url("/custom/custom/c-1"))
    # 検証
    expect(_heading(page, 2)).to_have_text("カスタムの見出し カスタム 1")
    page.goto(served.url("/custom/docs/doc-2"))
    expect(_heading(page)).to_have_text("文書 2")
    page.goto(served.url("/custom/guide/files/guide/intro"))
    expect(page.locator("main table").first.locator("th")).to_have_text(["colA", "colB"])
    expect(page.locator("main td")).to_have_text(["値A", "値B"])
    expect(page.get_by_role("main")).not_to_contain_text("embed:")


def test_error_when_converter_timed_out(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    page: Page,
) -> None:
    """制限時間を超えた変換のスクリプトは、本文の場所に失敗を出す（異常系）。"""
    # 準備
    files = _custom_files(sample_file_set, sample_config_text, SLEEP_SCRIPT)
    served = serve(make_source("custom", files), extra="script_timeout_sec: 1\n")
    # 実行
    page.goto(served.url("/custom/custom/c-1"))
    # 検証
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("本文を変換できませんでした")
    expect(alert).to_contain_text("制限時間を超えた")
    expect(alert.locator("dd").nth(0)).to_have_text("custom")
    expect(alert.locator("dd").nth(1)).to_contain_text("scripts/convert.py")
    expect(page.get_by_role("navigation", name="文書の種類")).to_be_visible()
    expect(page.get_by_role("navigation", name="文書の一覧")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("^検索"))).to_be_enabled()
    page.goto(served.url("/custom/docs/doc-2"))
    expect(_heading(page)).to_have_text("文書 2")


def test_error_when_doc_not_found(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """無い文書を開くと、見つからない画面で無いのが文書だと示す（異常系）。"""
    # 準備
    served = serve(make_source("sample", screen_files()))
    # 実行
    page.goto(served.url("/sample/no-such-doc"))
    # 検証
    expect(_heading(page)).to_have_text("文書が見つかりません")
    expect(page.locator("dd").filter(has_text="no-such-doc")).to_be_visible()
    expect(page.get_by_role("link", name="sample のトップを開く")).to_be_visible()


def test_error_when_ref_not_found(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """無いリビジョンを開くと、見つからない画面で無いのがリビジョンだと示す（異常系）。"""
    # 準備
    served = serve(make_source("sample", screen_files()))
    # 実行
    page.goto(served.url("/sample/docs/doc-1?rev=no-such-branch"))
    # 検証
    expect(_heading(page)).to_have_text("リビジョンが見つかりません")
    expect(page.locator("dd").filter(has_text="no-such-branch")).to_be_visible()


def test_error_when_source_not_served(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """配信していない配信元を開くと、外した理由を示す（異常系）。"""
    # 準備
    sample = make_source("sample", screen_files())
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, git=False)
    served = serve(sample, broken)
    # 実行
    page.goto(served.url("/broken/docs/doc-1"))
    # 検証
    expect(_heading(page)).to_have_text("配信元 broken を配信していません")
    expect(page.locator("dd").filter(has_text="documents[0].paths")).to_be_visible()
    expect(page.get_by_role("link", name="設定を開く")).to_be_visible()
    page.get_by_role("button", name=re.compile("^配信元を切り替える")).click()
    expect(page.get_by_role("menuitem", name=re.compile("sample"))).to_be_visible()
