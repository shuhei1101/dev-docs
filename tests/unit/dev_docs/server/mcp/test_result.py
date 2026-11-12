from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from mcp.types import TextContent
from pydantic import ValidationError

from dev_docs.features.admin.types import FormatRequest
from dev_docs.server.mcp.result import mcp_prompt_ids, to_tool_result, tool_error, tool_prompt_id
from dev_docs.shared.errors import ProjectIndexUnreachableError

ADDRESS = "http://127.0.0.1:8786"
REFUSED = "接続を拒否されました（Connection refused）"


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


def test_tool_error() -> None:
    """DevDocsError（正常系）。"""
    # 準備
    error = ProjectIndexUnreachableError(address=ADDRESS, reason=REFUSED)
    # 実行
    result = tool_error(error)
    # 検証
    text = _text(result.content[0])
    assert result.is_error is True
    assert text.splitlines()[0].startswith(
        f"ProjectIndexUnreachableError: project-index（{ADDRESS}）に接続できませんでした。"
    )
    assert ADDRESS in text
    assert REFUSED in text


def test_tool_error_when_validation() -> None:
    """引数の誤り（正常系）。"""
    # 準備
    with pytest.raises(ValidationError) as exc_info:
        FormatRequest(format="x")  # type: ignore[arg-type]
    # 実行
    result = tool_error(exc_info.value)
    # 検証
    assert "format:" in _text(result.content[0])


def test_tool_prompt_id() -> None:
    """ツール名からプロンプトの ID を作る（正常系）。"""
    # 実行
    result = tool_prompt_id("admin", "status")
    # 検証
    assert result == "mcp/admin/tools/status"


def test_mcp_prompt_ids() -> None:
    """管理の MCP の 3 つのツール（正常系）。"""
    # 実行
    result = mcp_prompt_ids()
    # 検証
    assert list(result) == [
        "mcp/admin/tools/status",
        "mcp/admin/tools/restart",
        "mcp/admin/tools/update",
    ]
