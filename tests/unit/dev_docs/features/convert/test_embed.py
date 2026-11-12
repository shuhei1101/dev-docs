from __future__ import annotations

from dev_docs.features.convert.embed import embed_paths, expand_embeds

LIST_VALUE = {"items": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}


def test_embed_paths() -> None:
    """重ねず、配信元の外とコードブロックを除く（正常系）。"""
    # 準備
    markdown = (
        "<!-- embed: data/a.yaml#x -->\n"
        "<!-- embed: data/a.yaml#y -->\n"
        "<!-- embed: ../x.yaml -->\n"
        "```text\n<!-- embed: data/b.yaml -->\n```\n"
    )
    # 実行
    result = embed_paths(markdown)
    # 検証
    assert result == ["data/a.yaml"]


def test_expand_embeds() -> None:
    """表に置き換える（正常系）。"""
    # 準備
    markdown = "# T\n\n<!-- embed: data/list.yaml#items -->\n"
    # 実行
    result = expand_embeds(markdown, {"data/list.yaml": LIST_VALUE})
    # 検証
    assert "| a | A |" in result
    assert "| b | B |" in result
    assert "<!-- embed:" not in result


def test_expand_embeds_when_in_code_block() -> None:
    """コードブロックの中は置き換えない（正常系）。"""
    # 準備
    markdown = "```text\n<!-- embed: data/list.yaml#items -->\n```\n"
    # 実行
    result = expand_embeds(markdown, {"data/list.yaml": LIST_VALUE})
    # 検証
    assert result == markdown


def test_expand_embeds_when_missing() -> None:
    """取れなかったパス（正常系）。"""
    # 準備
    markdown = "<!-- embed: none.yaml -->\n"
    # 実行
    result = expand_embeds(markdown, {"none.yaml": None})
    # 検証
    assert "> [!WARNING]\n> 埋め込めません: none.yaml" in result
