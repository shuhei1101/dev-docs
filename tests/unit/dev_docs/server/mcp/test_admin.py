from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from mcp.types import CallToolResult, TextContent

from dev_docs.features.lifecycle.control import RestartControl
from dev_docs.server.mcp.admin import build_admin_mcp
from dev_docs.server.mcp.result import tool_prompt_id

from ...conftest import FakeIndex

TOOL_NAMES = {"status", "restart", "update"}


def test_build_admin_mcp(make_mcp_handlers: Callable[..., Any]) -> None:
    """ツールと注釈（正常系）。"""
    # 準備
    mcp = build_admin_mcp(make_mcp_handlers())
    # 実行
    tools = asyncio.run(mcp.list_tools())
    # 検証
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == TOOL_NAMES
    assert {
        name: by_name[name].annotations.destructive_hint  # type: ignore[union-attr]
        for name in ("restart", "update")
    } == {"restart": True, "update": True}
    assert by_name["status"].annotations.read_only_hint is True  # type: ignore[union-attr]


def test_build_admin_mcp_when_status(
    fake_index: FakeIndex, make_mcp_handlers: Callable[..., Any]
) -> None:
    """状態を JSON で返す（正常系）。"""
    # 準備
    fake_index.sources = [{"id": "sample", "status": "serving", "errors": []}]
    mcp = build_admin_mcp(make_mcp_handlers())
    # 実行
    result = asyncio.run(mcp.call_tool("status", {"format": "json"}))
    # 検証
    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    assert result.structured_content is not None
    assert {"project_index", "sources"} <= set(result.structured_content)


def test_build_admin_mcp_when_restart_in_progress(make_mcp_handlers: Callable[..., Any]) -> None:
    """再起動の途中をエラーにする（正常系）。"""
    # 準備
    control = RestartControl()
    control.attach(cast("Any", SimpleNamespace(should_exit=False)))
    mcp = build_admin_mcp(make_mcp_handlers(restart=control))
    # 実行
    first = asyncio.run(mcp.call_tool("restart", {}))
    second = asyncio.run(mcp.call_tool("restart", {}))
    # 検証
    assert isinstance(first, CallToolResult)
    assert isinstance(second, CallToolResult)
    assert first.structured_content is not None
    assert first.structured_content["restarting"] is True
    assert second.is_error is True
    assert isinstance(second.content[0], TextContent)
    assert second.content[0].text.startswith("RestartInProgressError")


def test_build_admin_mcp_when_descriptions(
    make_mcp_handlers: Callable[..., Any], bundled_prompts: Any
) -> None:
    """ツールの説明をプロンプトの YAML から描画する（正常系）。"""
    from mcp import Client

    # 準備
    mcp = build_admin_mcp(make_mcp_handlers())

    async def _initialize() -> str | None:
        async with Client(mcp) as client:
            return client.instructions

    # 実行
    tools = asyncio.run(mcp.list_tools())
    instructions = asyncio.run(_initialize())
    # 検証
    assert {tool.name: tool.description for tool in tools} == {
        name: bundled_prompts.render(tool_prompt_id("admin", name)) for name in TOOL_NAMES
    }
    assert instructions is None
