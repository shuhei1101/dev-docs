"""ツールの結果とエラーの変換。"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Literal

from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import ValidationError
from ruamel.yaml import YAML

from dev_docs.shared.errors import DevDocsError

TOOL_ANNOTATIONS = {
    "status": ToolAnnotations(read_only_hint=True),
    "restart": ToolAnnotations(read_only_hint=False, destructive_hint=True),
    "update": ToolAnnotations(read_only_hint=False, destructive_hint=True),
}

# 管理の MCP が登録するツールの名前（登録の順）
ADMIN_TOOL_NAMES = ("status", "restart", "update")


def tool_prompt_id(server: str, tool: str) -> str:
    """ツールの description を描画するプロンプトの ID を作る（プロンプトの ID はハイフンだけを許す）。"""
    return f"mcp/{server}/tools/{tool.replace('_', '-')}"


def mcp_prompt_ids() -> list[str]:
    """管理の MCP が描画するプロンプトの ID を並べる。"""
    return [tool_prompt_id("admin", name) for name in ADMIN_TOOL_NAMES]


def _fields(value: Any) -> dict[str, Any]:
    """dataclass のフィールドを、JSON に出さない内部のフィールドを除いて辞書にする。"""
    return {
        item.name: getattr(value, item.name)
        for item in dataclasses.fields(value)
        if not item.metadata.get("internal")
    }


def _plain(value: Any) -> Any:
    """結果を JSON にできる辞書・配列・文字列にする（`None` と空の値は落とす）。"""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _plain(_fields(value))
    if isinstance(value, dict):
        cleaned = {str(key): _plain(item) for key, item in value.items() if item is not None}
        return {key: item for key, item in cleaned.items() if item not in ("", [], {})}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def to_tool_result(
    result: Any,
    fmt: Literal["markdown", "json"],
    render: Callable[[Any], str] | None,
) -> CallToolResult:
    """サービスの結果を `format` に合わせて MCP の `CallToolResult` にする。"""
    if fmt == "markdown" and render is not None:
        return CallToolResult(content=[TextContent(type="text", text=render(result))])
    data = _plain(result)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=data)


def _yaml(value: dict[str, Any]) -> str:
    """辞書を YAML の文字列にする。"""
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    stream = StringIO()
    yaml.dump(value, stream)
    return stream.getvalue().rstrip("\n")


def tool_error(error: DevDocsError | ValidationError) -> CallToolResult:
    """`DevDocsError` と要求のモデルの検証の誤りを `isError: true` の結果にする。"""
    if isinstance(error, ValidationError):
        lines = ["InvalidArgumentError: 引数が正しくありません"]
        lines.extend(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
    else:
        lines = [f"{error.name}: {error.message}"]
        details = _plain(error.details())
        if details:
            lines.append(_yaml(details))
        lines.extend(f"- {step}" for step in error.next_steps)
    return CallToolResult(content=[TextContent(type="text", text="\n".join(lines))], is_error=True)
