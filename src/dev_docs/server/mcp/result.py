"""ツールの結果とエラーの変換。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from mcp.types import CallToolResult, ToolAnnotations
from pydantic import ValidationError

from dev_docs.shared.errors import DevDocsError

TOOL_ANNOTATIONS = {
    "search_docs": ToolAnnotations(read_only_hint=True),
    "describe": ToolAnnotations(read_only_hint=True),
    "list_changes": ToolAnnotations(read_only_hint=True),
    "trace_related": ToolAnnotations(read_only_hint=True),
    "write_docs": ToolAnnotations(read_only_hint=False, destructive_hint=False),
    "delete_docs": ToolAnnotations(read_only_hint=False, destructive_hint=True),
}


def to_tool_result(
    result: Any,
    fmt: Literal["markdown", "json"],
    render: Callable[[Any], str] | None,
) -> CallToolResult:
    """サービスの結果を `format` に合わせて MCP の `CallToolResult` にする。"""
    raise NotImplementedError


def tool_error(error: DevDocsError | ValidationError) -> CallToolResult:
    """`DevDocsError` と要求のモデルの検証の誤りを `isError: true` の結果にする。"""
    raise NotImplementedError
