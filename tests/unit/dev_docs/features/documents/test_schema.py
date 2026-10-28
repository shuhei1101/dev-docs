from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.documents.schema import resolve_schema_refs

COMMON_SCHEMA = "$defs:\n  markdown:\n    type: string\n    title: Markdown\n"


def test_resolve_schema_refs(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """同じファイルと別のファイルの参照（正常系）。"""
    # 準備
    write_files(tmp_path, {"schemas/共通.schema.yaml": COMMON_SCHEMA})
    schema = {
        "$defs": {"x": {"type": "integer"}},
        "properties": {
            "a": {"$ref": "#/$defs/x"},
            "b": {"$ref": "共通.schema.yaml#/$defs/markdown", "title": "B"},
        },
    }
    # 実行
    result = resolve_schema_refs(schema, tmp_path / "schemas" / "rule.schema.yaml")
    # 検証
    assert result["properties"]["a"] == {"type": "integer"}
    assert result["properties"]["b"] == {"type": "string", "title": "B"}


def test_resolve_schema_refs_when_cycle(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """循環する参照（正常系）。"""
    # 準備
    schema = {
        "$defs": {
            "node": {
                "type": "object",
                "properties": {"children": {"items": {"$ref": "#/$defs/node"}}},
            }
        },
        "properties": {"root": {"$ref": "#/$defs/node"}},
    }
    # 実行
    with caplog.at_level(logging.WARNING):
        result = resolve_schema_refs(schema, tmp_path / "rule.schema.yaml")
    # 検証
    children = result["properties"]["root"]["properties"]["children"]
    assert children["items"] == {"$ref": "#/$defs/node"}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_resolve_schema_refs_when_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """参照先が無い（正常系）。"""
    # 準備
    schema = {"properties": {"a": {"$ref": "無い.schema.yaml#/$defs/x"}}}
    # 実行
    with caplog.at_level(logging.WARNING):
        result = resolve_schema_refs(schema, tmp_path / "rule.schema.yaml")
    # 検証
    assert result["properties"]["a"] == {"$ref": "無い.schema.yaml#/$defs/x"}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
