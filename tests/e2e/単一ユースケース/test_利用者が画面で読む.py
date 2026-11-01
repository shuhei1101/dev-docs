from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, ViewportSize, expect

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
TAG_NAV = (
    "nav:\n"
    "  tabs:\n"
    "    - title: mcp\n"
    "      items:\n"
    "        - auto:\n"
    "            document: sample\n"
    "            filter:\n"
    "              and:\n"
    "                - {field: tags, op: eq, values: [mcp]}\n"
    "                - not: {field: tags, op: eq, values: [設計]}\n"
    "    - title: すべて\n"
    "      items:\n"
    "        - auto:\n"
    "            document: sample\n"
)
TERM_ROW = (
    "  - id: terms\n"
    "    paths: [terms/*.yaml]\n"
    "    schema: schemas/term.schema.yaml\n"
    "    alias_type: term\n"
)
TERM_SCHEMA = "title: 用語\ntype: object\n"
SCOPE_TERM = "id: scope\nname: 作業範囲\ndescription: 触ってよい範囲\naliases: [scope, 担当範囲]\n"
TERM_NOTE = "# A\n\n担当範囲の中だけを書き換える。\n"
SLEEP_SCRIPT = "import time\ntime.sleep(60)\n"
SMALL_ROWS = [{"key": "k1", "label": "名称 1", "notes": "備考 1"}]
REFLECTION_PATH = "/sample/content/prompts/node/reflection"
SESSION_CONTEXT_PATH = "/sample/plugins/sample/content/prompts/session-context"
# 振り返りのノードの言語のタブ群の数（テンプレートの部品 5・例の組 2）
REFLECTION_TAB_GROUPS = 7
VIEWPORTS: tuple[ViewportSize, ...] = (
    {"width": 1280, "height": 800},
    {"width": 390, "height": 844},
)
# 本文の外の参照先の YAML の値を見出しに出す変換のスクリプト
REF_SCRIPT = (
    "import pathlib, sys\n"
    "sys.stdin.read()\n"
    "value = pathlib.Path('data/ref.yaml').read_text(encoding='utf-8').split(':', 1)[1].strip()\n"
    "print(f'## 参照先 {value}')\n"
)
CACHE_EXTRA = (
    "  - id: custom\n"
    "    paths: [custom/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    converter: ref\n"
    "converters:\n"
    "  - id: ref\n"
    "    run: [python3, scripts/ref.py]\n"
)


def _ref_files(
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    cache_line: str,
) -> dict[str, str]:
    """本文の外の参照先の YAML を読む変換を持つ配信元のファイル一式を返す。"""
    return sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(CACHE_EXTRA + cache_line, name="custom"),
            "scripts/ref.py": REF_SCRIPT,
            "custom/c-1.yaml": "id: c-1\nname: カスタム 1\n",
            "data/ref.yaml": "value: 前の値\n",
        }
    )


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


def _section(page: Page, name: str) -> Locator:
    """本文の、見出しの名前のセクションの中身のロケータを返す。"""
    return page.locator(f'main [id="section-{name}"]')


def _section_toggle(page: Page, name: str) -> Locator:
    """本文の、見出しの名前のセクションを開閉するボタンのロケータを返す。"""
    return page.get_by_role("main").get_by_role("button", name=name, exact=True)


def _group_links(page: Page, group: str) -> Locator:
    """サイドバーの、`group` の見出しの下の文書のリンクのロケータを返す。"""
    sidebar = page.get_by_role("navigation", name="文書の一覧")
    return (
        sidebar.locator("li:has(> p)")
        .filter(has=page.locator("p", has_text=re.compile(f"^{group}$")))
        .get_by_role("link")
    )


def _selected_tabs(page: Page, name: str) -> Locator:
    """本文の、選ばれている `name` の言語のタブのロケータを返す（閉じたセクションの中も含む）。"""
    return page.locator('main [role="tab"][aria-selected="true"]').filter(
        has_text=re.compile(f"^{name}$")
    )


def _fits_width(page: Page) -> bool:
    """文書が画面の幅に収まり、横にはみ出していないかを返す。"""
    return bool(
        page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
    )


def _fits_all_viewports(page: Page) -> list[bool]:
    """`VIEWPORTS` の画面幅ごとに、文書が横にはみ出していないかを返す。"""
    results = []
    for size in VIEWPORTS:
        page.set_viewport_size(size)
        expect(_heading(page)).to_be_visible()
        results.append(_fits_width(page))
    return results


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
    page.goto(served.url("/sample/guide/files/guide/table.md"))
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
    page.goto(served.url("/sample/notes/files/notes/a.md"))
    expect(_heading(page)).to_have_text("a")
    # 実行
    page.get_by_role("main").get_by_role("link", name="B").click()
    # 検証
    expect(page).to_have_url(re.compile(r"/sample/notes/b\.md$"))
    expect(_heading(page)).to_have_text("b")
    expect(page.get_by_role("main")).to_contain_text("B の本文。")
    expect(page.get_by_role("main")).not_to_contain_text("文書が見つかりません")
    current = page.get_by_role("navigation", name="文書の一覧").locator('[aria-current="page"]')
    expect(current).to_have_attribute("href", re.compile(r"/notes/files/notes/b\.md$"))


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
    page.goto(served.url("/custom/guide/files/guide/intro.md"))
    expect(page.locator("main table").first.locator("th")).to_have_text(["colA", "colB"])
    expect(page.locator("main td")).to_have_text(["値A", "値B"])
    expect(page.get_by_role("main")).not_to_contain_text("embed:")


def test_normal_when_converter_cache_disabled(
    tmp_path: Path,
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    page: Page,
) -> None:
    """cache: false の変換は、開き直すたびにスクリプトを動かして参照先の今の内容を出す（正常系）。"""
    # 準備
    files = _ref_files(sample_file_set, sample_config_text, "    cache: false\n")
    source = make_source("custom", files, git=False)
    served = serve(source)
    page.goto(served.url("/custom/custom/c-1"))
    expect(_heading(page, 2)).to_have_text("参照先 前の値")
    (source.folder / "data" / "ref.yaml").write_text("value: 後の値\n", encoding="utf-8")
    # 実行
    page.goto(served.url("/custom/custom/c-1"))
    # 検証
    expect(_heading(page, 2)).to_have_text("参照先 後の値")
    assert list((tmp_path / "state" / "converted").glob("*.md")) == []


def test_normal_when_converter_cache_enabled(
    tmp_path: Path,
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    page: Page,
) -> None:
    """cache を書かない変換は控えを書き、開き直しても 1 回目と同じ本文を出す（正常系）。"""
    # 準備
    files = _ref_files(sample_file_set, sample_config_text, "")
    source = make_source("custom", files, git=False)
    served = serve(source)
    page.goto(served.url("/custom/custom/c-1"))
    expect(_heading(page, 2)).to_have_text("参照先 前の値")
    (source.folder / "data" / "ref.yaml").write_text("value: 後の値\n", encoding="utf-8")
    # 実行
    page.goto(served.url("/custom/custom/c-1"))
    # 検証
    expect(_heading(page, 2)).to_have_text("参照先 前の値")
    assert len(list((tmp_path / "state" / "converted").glob("*.md"))) == 1


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


def test_normal_when_nav_filtered_by_tags(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    sample_doc_text: Callable[..., str],
    page: Page,
) -> None:
    """nav の auto のタグの式に当たる文書だけをサイドバーに並べ、式の無いタブは全てを並べる（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(TAG_NAV),
            "docs/doc-1.yaml": sample_doc_text("doc-1", "文書 1", tags=["mcp"]),
            "docs/doc-2.yaml": sample_doc_text("doc-2", "文書 2", tags=["mcp", "設計"]),
            "docs/doc-3.yaml": sample_doc_text("doc-3", "文書 3", tags=["設計"]),
        }
    )
    served = serve(make_source("sample", files))
    tabs = page.get_by_role("navigation", name="文書の種類")
    sidebar = page.get_by_role("navigation", name="文書の一覧")
    # 実行
    page.goto(served.url("/sample"))
    expect(sidebar.get_by_role("link")).to_have_text(["文書 1"])
    _side_link(page, "文書 1").click()
    expect(_heading(page)).to_have_text("文書 1")
    tabs.get_by_role("link", name="すべて").click()
    # 検証
    expect(sidebar.get_by_role("link")).to_have_text(["文書 1", "文書 2", "文書 3"])


def test_normal_when_term_tooltip_shown(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    screen_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """本文の用語の語にポインタを載せると、用語のツールチップを出す（正常系）。"""
    # 準備
    notes = {
        "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
        "notes/files.yaml": "files:\n  - path: a.md\n",
        "notes/a.md": TERM_NOTE,
    }
    sample = make_source(
        "sample",
        screen_files(
            nav=False,
            config_extra=TERM_ROW + NOTES_EXTRA,
            **{"schemas/term.schema.yaml": TERM_SCHEMA, "terms/scope.yaml": SCOPE_TERM, **notes},
        ),
    )
    plain = make_source("plain", screen_files(nav=False, config_extra=NOTES_EXTRA, **notes))
    served = serve(sample, plain)
    term = page.get_by_role("main").get_by_text("担当範囲", exact=True)
    # 実行
    document = served.get("/_api/sources/sample/docs/docs/doc-1")
    page.goto(served.url("/sample/notes/files/notes/a.md"))
    expect(_heading(page)).to_have_text("a")
    term.hover()
    tooltip = page.get_by_role("tooltip")
    expect(tooltip).to_be_visible()
    # 検証
    aliases = {item["name"]: item for item in document.json()["aliases"]}
    assert aliases["作業範囲"]["aliases"] == ["scope", "担当範囲"]
    assert aliases["作業範囲"]["description"] == "触ってよい範囲"
    expect(tooltip).to_contain_text("用語")
    expect(tooltip).to_contain_text("触ってよい範囲")
    page.goto(served.url("/plain/notes/files/notes/a.md"))
    expect(page.get_by_role("main")).to_contain_text("担当範囲の中だけを書き換える。")
    page.get_by_role("main").get_by_text("担当範囲の中だけを書き換える。").hover()
    expect(page.get_by_role("tooltip")).to_have_count(0)


def test_normal_when_prompt_document(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    prompt_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """プロンプトを、変数の表・テンプレート・例の組と言語のタブで出す（正常系）。"""
    # 準備
    served = serve(make_source("sample", prompt_files()))
    tabs = page.get_by_role("navigation", name="文書の種類")
    main = page.get_by_role("main")
    # 実行
    page.goto(served.url("/sample"))
    tabs.get_by_role("link", name="プロンプト").click()
    # 検証
    expect(_group_links(page, "llm")).to_have_text(["振り返りのノード"])
    expect(_group_links(page, "hook")).to_have_text(["SessionStart の配信元の一覧"])
    _group_links(page, "llm").click()
    expect(page).to_have_url(re.compile(f"{REFLECTION_PATH}$"))
    # 見出し・バッジ・説明
    expect(_heading(page)).to_have_text("振り返りのノード")
    expect(main.locator(".mdmark > p").first.locator(".mdmark-badge")).to_have_text(
        ["kind: llm", "lang: en"]
    )
    expect(main).to_contain_text(
        "キャラクターが最近の出来事を振り返り、性格特性の基底値の変化を決める"
    )
    # 変数の表
    variables = _section(page, "変数").locator("table")
    expect(variables.locator("th")).to_have_text(["変数", "型", "必須", "例", "説明", "出どころ"])
    expect(
        variables.locator("td code").filter(has_text=re.compile(r"^character\.display_name$"))
    ).to_be_visible()
    expect(
        variables.locator("td code").filter(has_text=re.compile(r"^traits\[\]\.name$"))
    ).to_be_visible()
    # テンプレートの部品（role・when）と、Jinja2 のままの本文
    expect(_section(page, "role").locator(".mdmark-badge")).to_contain_text(["role: system"])
    expect(_section(page, "logs").locator(".mdmark-badge")).to_contain_text(
        ["when: {{ logs | length > 0 }}"]
    )
    expect(_section(page, "traits").locator("pre").first).to_contain_text("{% for t in traits -%}")
    hint = (
        _section(page, "role")
        .locator("span[data-hint]")
        .filter(has_text="{{ character.display_name }}")
    )
    hint.first.focus()
    expect(page.get_by_role("tooltip")).to_have_text("表示名（型: string、例: ひな）")
    page.keyboard.press("Escape")
    # 例の組
    expect(_section_toggle(page, "既定の例")).to_have_attribute("aria-expanded", "true")
    expect(_section_toggle(page, "ログが無い")).to_have_attribute("aria-expanded", "false")
    default_example = _section(page, "既定の例")
    expect(default_example.locator("strong")).to_contain_text(["system", "user"])
    expect(default_example).to_contain_text(re.compile(r"[\d,]+ 字 / 使わなかった部品: no-logs"))
    # 言語のタブを ja にすると全てのセクションが揃って ja になる
    expect(_section(page, "role").get_by_role("tab")).to_have_text(["en", "ja"])
    _section(page, "role").get_by_role("tab", name="ja").click()
    expect(_selected_tabs(page, "ja")).to_have_count(REFLECTION_TAB_GROUPS)
    expect(_selected_tabs(page, "en")).to_have_count(0)
    expect(_section(page, "role").locator("pre:visible")).to_contain_text("### 役割")
    # 閉じた組を開くと、ja で描画した結果が出る
    _section_toggle(page, "ログが無い").click()
    no_logs = _section(page, "ログが無い")
    expect(no_logs.locator("pre:visible").first).to_contain_text("### 役割")
    expect(no_logs.locator("pre:visible").last).to_contain_text("- なし")
    expect(no_logs).to_contain_text(re.compile(r"[\d,]+ 字 / 使わなかった部品: logs"))
    # 開き直しても ja のまま
    page.reload()
    expect(_heading(page)).to_have_text("振り返りのノード")
    expect(_selected_tabs(page, "ja")).to_have_count(REFLECTION_TAB_GROUPS)
    # 画面幅 1280 と 390 で横にはみ出さない
    assert _fits_all_viewports(page) == [True, True]


def test_normal_when_prompt_set_flagged(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    prompt_files: Callable[..., dict[str, str]],
    page: Page,
) -> None:
    """型の合わない組に注意書き、字数を超える hook の組に注意を出し、他は描く（正常系）。"""
    # 準備
    served = serve(make_source("sample", prompt_files(broken=True, many_sources=True)))
    main = page.get_by_role("main")
    # 実行
    page.goto(served.url(REFLECTION_PATH))
    _section_toggle(page, "broken").click()
    # 検証
    broken = _section(page, "broken")
    cautions = broken.locator(".markdown-alert-caution")
    expect(cautions).to_have_count(2)
    expect(cautions.first).to_contain_text("この組は描画できません。")
    expect(cautions.first).to_contain_text("traits は array ですが、oops が入っています")
    expect(cautions.last).to_contain_text("traits は array ですが、oops が入っています")
    broken.get_by_role("tab", name="ja").click()
    expect(cautions.last).to_be_visible()
    # 他の組・変数の表・テンプレートは描かれる
    expect(_section(page, "既定の例")).to_contain_text(
        re.compile(r"[\d,]+ 字 / 使わなかった部品: no-logs")
    )
    expect(_section(page, "ログが無い")).to_contain_text(
        re.compile(r"[\d,]+ 字 / 使わなかった部品: logs")
    )
    expect(_section(page, "変数").locator("table")).to_be_visible()
    expect(_section(page, "role").locator("pre:visible")).to_contain_text(
        "{{ character.display_name }}"
    )
    # kind: llm の組には字数の注意が出ない
    expect(main.locator(".markdown-alert-warning")).to_have_count(0)
    # hook の字数を超える組に注意と描画した結果が出る
    page.goto(served.url(SESSION_CONTEXT_PATH))
    expect(_heading(page)).to_have_text("SessionStart の配信元の一覧")
    _section_toggle(page, "many-sources").click()
    many_sources = _section(page, "many-sources")
    expect(many_sources.locator(".markdown-alert-warning")).to_contain_text(
        re.compile(r"注入する本文が [\d,]+ 字で、上限の 1,000 字を超えています。")
    )
    expect(many_sources.locator("pre")).to_contain_text("source-20")
    # 1,000 字以下の組には注意が出ず、言語が ja だけの文書には言語のタブが出ない
    expect(main.locator(".markdown-alert-warning")).to_have_count(1)
    expect(main.get_by_role("tablist")).to_have_count(0)
    expect(_section(page, "既定の例").locator("pre")).to_contain_text(
        "dev-docs で次の配信元を使えます。"
    )
