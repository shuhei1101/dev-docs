from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from mcp.types import TextContent
from pydantic import ValidationError

from dev_docs.features.access.types import SourceAccess
from dev_docs.features.search.types import SearchItem, SearchRequest, SearchResult
from dev_docs.server.mcp.result import to_tool_result, tool_error
from dev_docs.shared.errors import SourceNotReadableError


@dataclass
class Sample:
    """結果の dataclass の例。"""

    value: str
    skipped: str | None = None


def _text(content: object) -> str:
    """ツールの結果の text を取り出す。"""
    assert isinstance(content, TextContent)
    return content.text


def test_to_tool_result() -> None:
    """markdown（正常系）。"""
    # 実行
    result = to_tool_result(Sample("x"), "markdown", lambda value: "# x")
    # 検証
    assert _text(result.content[0]) == "# x"
    assert result.structured_content is None


def test_to_tool_result_when_json() -> None:
    """json（正常系）。"""
    # 実行
    result = to_tool_result(Sample("x"), "json", lambda value: "# x")
    # 検証
    assert result.structured_content == {"value": "x"}
    assert json.loads(_text(result.content[0])) == result.structured_content


def test_to_tool_result_when_location() -> None:
    """場所と範囲は項目の直下（正常系）。"""
    # 準備
    items = [
        SearchItem(
            id="src/a",
            source=None,
            values={"path": "a.py", "name": "a"},
            path="/ws/src/a.py",
            scope="full",
        ),
        SearchItem(id="doc-2", source=None, values={"name": "文書 2"}),
    ]
    search = SearchResult(total_count=2, returned=2, view="full", items=items)
    # 実行
    result = to_tool_result(search, "json", None)
    # 検証
    assert result.structured_content is not None
    first, second = result.structured_content["items"]
    assert first["path"] == "/ws/src/a.py"
    assert first["scope"] == "full"
    assert first["values"]["path"] == "a.py"
    assert "path" not in second
    assert "scope" not in second
    assert "path" not in second["values"]


def test_tool_error() -> None:
    """DevDocsError（正常系）。"""
    # 準備
    error = SourceNotReadableError(
        message="other は読めません",
        available=[
            SourceAccess(source_id="sample", access="write", current=True, description="サンプル")
        ],
        next_steps=["describe() で使える配信元を見てください"],
    )
    # 実行
    result = tool_error(error)
    # 検証
    text = _text(result.content[0])
    assert result.is_error is True
    assert text.splitlines()[0].startswith("SourceNotReadableError:")
    assert "sample" in text


def test_tool_error_when_validation() -> None:
    """引数の誤り（正常系）。"""
    # 準備
    with pytest.raises(ValidationError) as exc_info:
        SearchRequest(limit="x")  # type: ignore[arg-type]
    # 実行
    result = tool_error(exc_info.value)
    # 検証
    text = _text(result.content[0])
    assert "limit:" in text
    assert "describe" in text
