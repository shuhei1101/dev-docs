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

from dev_docs.features.changes.types import ChangesResult, ContainsChange
from dev_docs.features.related.types import RelatedItem
from dev_docs.features.search.types import SearchItem, SnippetLine
from dev_docs.features.write.types import DeleteResult
from dev_docs.shared.errors import DevDocsError

TOOL_ANNOTATIONS = {
    "search_docs": ToolAnnotations(read_only_hint=True),
    "describe": ToolAnnotations(read_only_hint=True),
    "list_changes": ToolAnnotations(read_only_hint=True),
    "trace_related": ToolAnnotations(read_only_hint=True),
    "write_docs": ToolAnnotations(read_only_hint=False, destructive_hint=False),
    "delete_docs": ToolAnnotations(read_only_hint=False, destructive_hint=True),
    "status": ToolAnnotations(read_only_hint=True),
    "reload": ToolAnnotations(read_only_hint=False, destructive_hint=False),
    "restart": ToolAnnotations(read_only_hint=False, destructive_hint=True),
    "update": ToolAnnotations(read_only_hint=False, destructive_hint=True),
    "check_project": ToolAnnotations(read_only_hint=True),
    "try_convert": ToolAnnotations(read_only_hint=True),
}

DESCRIBE_HINT = "describe で使い方（使える配信元・種類・スキーマ）を見てください"


def _fields(value: Any) -> dict[str, Any]:
    """dataclass のフィールドを、JSON に出さない内部のフィールドを除いて辞書にする。"""
    return {
        item.name: getattr(value, item.name)
        for item in dataclasses.fields(value)
        if not item.metadata.get("internal")
    }


def _plain(value: Any) -> Any:
    """結果を JSON にできる辞書・配列・文字列にする（`None` と空の値は落とす）。"""
    if isinstance(value, ChangesResult):
        data = _fields(value)
        data["range"] = {"from": data.pop("range_from"), "to": data.pop("range_to")}
        return _plain(data)
    if isinstance(value, RelatedItem):
        data = _fields(value)
        data["via"] = {
            "from": data.pop("via_from"),
            "type": data.pop("via_type"),
            "direction": data.pop("via_direction"),
        }
        return _plain(data)
    if isinstance(value, DeleteResult):
        data = _fields(value)
        data["unlinked"] = [
            {"id": doc_id, "version": version} for doc_id, version in value.unlinked
        ]
        return _plain(data)
    if isinstance(value, ContainsChange):
        data = _fields(value)
        data["from"] = data.pop("from_")
        return _plain(data)
    if isinstance(value, SearchItem):
        data = _plain(_fields(value))
        if value.ranges is not None:
            # 返す行が無くても、切り出したことが分かるよう `ranges: []` を出す
            data["ranges"] = [_plain(item) for item in value.ranges]
        return data
    if isinstance(value, SnippetLine):
        # 空の行も `line`・`text`・`hit` を全て出す
        return {"line": value.line, "text": value.text, "hit": value.hit}
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
        lines.append(f"- {DESCRIBE_HINT}")
    else:
        lines = [f"{error.name}: {error.message}"]
        details = _plain(error.details())
        if details:
            lines.append(_yaml(details))
        lines.extend(f"- {step}" for step in error.next_steps)
    return CallToolResult(content=[TextContent(type="text", text="\n".join(lines))], is_error=True)
