from __future__ import annotations

from dev_docs.features.convert.inline import (
    heading_anchor,
    link_decisions,
    link_reference,
    rewrite_text,
)
from dev_docs.features.convert.types import DiagramHead, DocumentLink, RenderContext

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")
CONTEXT = RenderContext(
    links={"dev/a": DocumentLink(title="A", path="dev/a.yaml")},
    issue_url="https://github.com/o/r/issues/",
    path="dev/b.yaml",
)
NO_ISSUE = RenderContext(links={}, issue_url=None, path="dev/b.yaml")
ID_LINKS = {
    "a": DocumentLink(title="A", path="dev/a.yaml"),
    "b": DocumentLink(title="B", path="dev/b.yaml"),
}


def _flow_heading(document_id: str, item: str) -> str | None:
    """文書 `b` の項目 `flow` だけが見出し `処理の流れ` を持つ、項目の見出しの引き方。"""
    return "処理の流れ" if (document_id, item) == ("b", "flow") else None


def _section_heading(document_id: str, item: str) -> str | None:
    """文書 `dev/a` の項目 `flows[正常系]` だけが見出し `正常系` を持つ、項目の見出しの引き方。"""
    return "正常系" if (document_id, item) == ("dev/a", "flows[正常系]") else None


ID_CONTEXT = RenderContext(
    links=ID_LINKS, issue_url=None, path="dev/c.yaml", item_heading=_flow_heading
)


def test_rewrite_text_when_mermaid() -> None:
    """中の図を map の範囲にする（正常系）。"""
    # 準備
    text = "前の段落\n\n```mermaid\nsequenceDiagram\n  A->>B: 読む\n```\n\n後の段落"
    # 実行
    result = rewrite_text(text, CONTEXT, HEAD)
    # 検証
    assert result.startswith("前の段落")
    assert result.endswith("後の段落")
    assert '<!-- map: {"title": ' in result
    assert "<!-- /map -->" in result


def test_rewrite_text_when_tree() -> None:
    """ファイルツリー（正常系）。"""
    # 準備
    text = "```\nsrc/\n├── a.py\n└── b.py\n```"
    # 実行
    result = rewrite_text(text, CONTEXT, HEAD)
    # 検証
    assert result == "```tree\nsrc/\n├── a.py\n└── b.py\n```"


def test_rewrite_text_when_steps() -> None:
    """手順（正常系）。"""
    # 実行
    result = rewrite_text("1. 開く\n2. 読む", CONTEXT, HEAD)
    # 検証
    assert result == "<!-- steps -->\n\n1. 開く\n2. 読む\n\n<!-- /steps -->"


def test_rewrite_text_when_issue() -> None:
    """Issue 番号（正常系）。"""
    # 実行
    result = rewrite_text("#26 で直す。`#27` は残す", CONTEXT, HEAD)
    # 検証
    assert result == "[#26](https://github.com/o/r/issues/26) で直す。`#27` は残す"


def test_rewrite_text_when_heading_link() -> None:
    """見出しへのリンク先の `#`（正常系）。"""
    # 実行
    result = rewrite_text("[手順](#1-手順) と #26", CONTEXT, HEAD)
    # 検証
    assert result == "[手順](#1-手順) と [#26](https://github.com/o/r/issues/26)"


def test_rewrite_text_when_no_issue_url() -> None:
    """Issue の URL が無い（正常系）。"""
    # 実行
    result = rewrite_text("#26", NO_ISSUE, HEAD)
    # 検証
    assert result == "#26"


def test_rewrite_text_when_choices() -> None:
    """値の選択肢（正常系）。"""
    # 実行
    result = rewrite_text("'planned'（予定） / 'allowed'（許可）", CONTEXT, HEAD)
    # 検証
    assert result == "- `badge:planned` 予定\n- `badge:allowed` 許可"


def test_rewrite_text_when_id_link() -> None:
    """id のリンク（正常系）。"""
    # 準備
    text = "[A](id:a) と [B](id:b#flow) と [C](id:zzz) と `[D](id:a)`"
    # 実行
    result = rewrite_text(text, ID_CONTEXT, HEAD)
    # 検証
    assert result == "[A](a.yaml) と [B](b.yaml#処理の流れ) と [C](id:zzz) と `[D](id:a)`"


def test_rewrite_text_when_id_link_no_heading() -> None:
    """見出しにならない項目（正常系）。"""
    # 実行
    result = rewrite_text("[B](id:b#no-such)", ID_CONTEXT, HEAD)
    # 検証
    assert result == "[B](b.yaml)"


def test_link_reference() -> None:
    """項目を指す参照（正常系）。"""
    # 実行
    result = link_reference("dev/a#flows[正常系]", CONTEXT)
    # 検証
    assert result == "[A / flows\\[正常系\\]](a.yaml)"


def test_link_reference_when_heading() -> None:
    """見出しになる項目（正常系）。"""
    # 準備
    context = RenderContext(
        links=CONTEXT.links, issue_url=None, path="dev/b.yaml", item_heading=_section_heading
    )
    # 実行
    result = link_reference("dev/a#flows[正常系]", context)
    # 検証
    assert result == "[A / flows\\[正常系\\]](a.yaml#正常系)"


def test_link_reference_when_unknown() -> None:
    """引き先に無い（正常系）。"""
    # 実行
    result = link_reference("dev/z#x", CONTEXT)
    # 検証
    assert result is None


def test_link_decisions() -> None:
    """リンクにする ID とそれ以外（正常系）。"""
    # 準備
    context = RenderContext(
        links={}, issue_url=None, path="dev/a/b.yaml", decisions=frozenset({"D-1"})
    )
    # 実行
    result = link_decisions(["D-1", "D-2", 3], context)
    # 検証
    assert result == ["[D-1](../../_decisions/D-1)", "D-2", 3]


def test_heading_anchor() -> None:
    """記号と空白（正常系）。"""
    # 実行
    result = heading_anchor("正常シナリオ（ER 図を読む）")
    # 検証
    assert result == "正常シナリオer-図を読む"
