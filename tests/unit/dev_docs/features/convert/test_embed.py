from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dev_docs.features.convert.embed import expand_embeds


def test_expand_embeds(tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]) -> None:
    """表に置き換える（正常系）。"""
    # 準備
    write_files(
        tmp_path,
        {"data/list.yaml": "items:\n  - id: a\n    name: A\n  - id: b\n    name: B\n"},
    )
    markdown = "# T\n\n<!-- embed: data/list.yaml#items -->\n"
    # 実行
    result = expand_embeds(markdown, tmp_path)
    # 検証
    assert "| a | A |" in result
    assert "| b | B |" in result
    assert "<!-- embed:" not in result


def test_expand_embeds_when_in_code_block(tmp_path: Path) -> None:
    """コードブロックの中は置き換えない（正常系）。"""
    # 準備
    markdown = "```text\n<!-- embed: data/list.yaml#items -->\n```\n"
    # 実行
    result = expand_embeds(markdown, tmp_path)
    # 検証
    assert result == markdown


def test_expand_embeds_when_missing(tmp_path: Path) -> None:
    """無いファイルと配信元の外（正常系）。"""
    # 準備
    markdown = "<!-- embed: none.yaml -->\n\n<!-- embed: ../x.yaml -->\n"
    # 実行
    result = expand_embeds(markdown, tmp_path)
    # 検証
    assert result.count("埋め込めません") == 2
