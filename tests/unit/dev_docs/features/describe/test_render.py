from __future__ import annotations

from pathlib import Path

from dev_docs.features.access.types import SourceAccess, Workplace
from dev_docs.features.describe.render import render_describe_markdown
from dev_docs.features.describe.types import KindSchemaResult, OutsideSource, SourceListResult


def test_render_describe_markdown() -> None:
    """一覧の表（正常系）。"""
    # 準備
    result = SourceListResult(
        workplace=Workplace(cwd=Path("/w/sample"), source_id="sample", worktree=None),
        sources=[
            SourceAccess(source_id="sample", access="write", current=True, description="サンプル"),
            SourceAccess(source_id="notes", access="read", current=False, description="メモ"),
        ],
    )
    # 実行
    markdown = render_describe_markdown(result)
    # 検証
    assert "| sample | write（作業中） | サンプル |" in markdown
    assert "| notes | read | メモ |" in markdown


def test_render_describe_markdown_when_outside_sources() -> None:
    """作業範囲の外で読める配信元の表（正常系）。"""
    # 準備
    workplace = Workplace(cwd=Path("/w/sample"), source_id="sample", worktree=None)
    sources = [
        SourceAccess(source_id="sample", access="write", current=True, description="サンプル")
    ]
    result = SourceListResult(
        workplace=workplace,
        sources=sources,
        outside_sources=[OutsideSource(id="other", description="別の配信元")],
    )
    # 実行
    markdown = render_describe_markdown(result)
    plain = render_describe_markdown(SourceListResult(workplace=workplace, sources=sources))
    # 検証
    assert markdown.index("| sample | write（作業中） | サンプル |") < markdown.index(
        "作業範囲の外（参考）"
    )
    assert "| other | 別の配信元 |" in markdown
    assert "作業範囲の外（参考）" not in plain


def test_render_describe_markdown_when_outside_sources_empty() -> None:
    """作業範囲の外で読める配信元が 0 件（正常系）。"""
    # 準備
    result = SourceListResult(
        workplace=Workplace(cwd=Path("/w/sample"), source_id="sample", worktree=None),
        sources=[],
        outside_sources=[],
    )
    # 実行
    markdown = render_describe_markdown(result)
    # 検証
    lines = markdown.splitlines()
    index = lines.index("作業範囲の外（参考）")
    assert lines[index + 1] == "なし"
    assert "| source | description |" not in markdown


def test_render_describe_markdown_when_metadata() -> None:
    """メタデータの対応の表（正常系）。"""
    # 準備
    result = KindSchemaResult(
        source_id="sample",
        kind="rules",
        schema_text="type: object\n",
        schema={"type": "object"},
        metadata={"name": "title"},
    )
    # 実行
    markdown = render_describe_markdown(result)
    # 検証
    assert "| name | title |" in markdown
    assert markdown.index("| name | title |") < markdown.index("```yaml")


def test_render_describe_markdown_when_outside_scope() -> None:
    """作業範囲の外の表示（正常系）。"""
    from dev_docs.features.describe.types import KindSummary, SourceGuideResult

    # 準備
    result = SourceGuideResult(
        source_id="other",
        instructions="other の説明書",
        kinds=[KindSummary(id="rules", description="規約")],
        outside_scope=True,
        refs=None,
        worktrees=None,
    )
    # 実行
    markdown = render_describe_markdown(result)
    # 検証
    lines = markdown.splitlines()
    assert lines[0] == "作業範囲の外（参考）"
    assert "other の説明書" in lines[1:]
