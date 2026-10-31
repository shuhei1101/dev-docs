from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent

from dev_docs.features.search.types import SearchRequest, SearchResult
from dev_docs.server.mcp import docs as docs_module
from dev_docs.server.mcp.docs import build_docs_mcp
from dev_docs.shared.errors import UnknownKindError

TOOL_NAMES = {
    "search_docs",
    "write_docs",
    "delete_docs",
    "describe",
    "list_changes",
    "trace_related",
    "list_match_words",
}


def test_build_docs_mcp(make_handlers: Callable[..., Any]) -> None:
    """ツールと注釈（正常系）。"""
    # 準備
    mcp = build_docs_mcp(make_handlers())
    # 実行
    tools = asyncio.run(mcp.list_tools())
    # 検証
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == TOOL_NAMES
    assert by_name["delete_docs"].annotations is not None
    assert by_name["delete_docs"].annotations.destructive_hint is True
    assert by_name["search_docs"].annotations is not None
    assert by_name["search_docs"].annotations.read_only_hint is True
    assert by_name["list_match_words"].annotations is not None
    assert by_name["list_match_words"].annotations.read_only_hint is True


def test_build_docs_mcp_when_instructions(make_handlers: Callable[..., Any]) -> None:
    """タグの付け方の instructions（正常系）。"""
    from mcp import Client

    from dev_docs.features.session_context.types import TAG_GUIDE

    # 準備
    mcp = build_docs_mcp(make_handlers())

    async def _initialize() -> str | None:
        async with Client(mcp) as client:
            return client.instructions

    # 実行
    result = asyncio.run(_initialize())
    # 検証
    assert result == TAG_GUIDE


def test_build_docs_mcp_when_call(
    make_handlers: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """サービスへの受け渡し（正常系）。"""
    # 準備
    received: list[SearchRequest] = []

    def fake_search_docs(request: SearchRequest, **kwargs: Any) -> SearchResult:
        received.append(request)
        return SearchResult(total_count=0, returned=0, view="summary")

    monkeypatch.setattr(docs_module, "search_docs", fake_search_docs)
    mcp = build_docs_mcp(make_handlers())
    # 実行
    result = asyncio.run(mcp.call_tool("search_docs", {"source": "sample", "format": "json"}))
    # 検証
    assert isinstance(result, CallToolResult)
    assert received[0].source == "sample"
    assert result.is_error is False
    assert result.structured_content is not None


def test_build_docs_mcp_when_error(
    make_handlers: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """エラーの変換（正常系）。"""

    # 準備
    def failing_write_docs(*args: Any, **kwargs: Any) -> Any:
        raise UnknownKindError(message="種類がありません", kinds=["rules"])

    monkeypatch.setattr(docs_module, "write_docs", failing_write_docs)
    mcp = build_docs_mcp(make_handlers())
    arguments = {"operations": [{"op": "create", "kind": "x", "data": {}}]}
    # 実行
    result = asyncio.run(mcp.call_tool("write_docs", arguments))
    # 検証
    assert isinstance(result, CallToolResult)
    assert result.is_error is True
    assert isinstance(result.content[0], TextContent)
    assert "UnknownKindError" in result.content[0].text


def test_build_docs_mcp_when_descriptions(make_handlers: Callable[..., Any]) -> None:
    """追加した引数の説明（正常系）。"""
    # 準備
    mcp = build_docs_mcp(make_handlers())
    # 実行
    tools = asyncio.run(mcp.list_tools())
    # 検証
    by_name = {tool.name: tool for tool in tools}
    search_description = by_name["search_docs"].description or ""
    for word in (
        "not",
        "glob",
        "@matches",
        "sections",
        "lines",
        "describe(source, kind)",
        "group_by: tags",
    ):
        assert word in search_description
    assert "contains" in (by_name["list_changes"].description or "")
    assert "describe(source, kind)" in (by_name["write_docs"].description or "")
    search_properties = by_name["search_docs"].input_schema["properties"]
    changes_properties = by_name["list_changes"].input_schema["properties"]
    assert "description" in search_properties["sections"]
    assert "description" in search_properties["lines"]
    assert "description" in changes_properties["contains"]
