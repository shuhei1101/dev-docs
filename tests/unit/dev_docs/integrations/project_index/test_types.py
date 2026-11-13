from __future__ import annotations

import pytest

from dev_docs.integrations.project_index.types import parse_document
from dev_docs.shared.errors import ProjectIndexResponseError

from ...conftest import doc_json, list_entry


def test_parse_document() -> None:
    """文書の一覧の 1 件（正常系）。"""
    # 準備
    value = list_entry(
        doc_json(
            "n-1",
            "notes/files.yaml",
            kind="files",
            data={"path": "a.md"},
            metadata={"id": "n-1", "name": "N1", "tags": ["topic:a"], "visibility": "public"},
            body_path="notes/a.md",
            body="# A\n",
        ),
        values=True,
    )
    # 実行
    document = parse_document("sample", value, record_index=1)
    # 検証
    assert document.data == {"path": "a.md"}
    assert document.metadata == {
        "id": "n-1",
        "kind": "files",
        "name": "N1",
        "description": None,
        "tags": ["topic:a"],
        "visibility": "public",
    }
    assert document.body_path == "notes/a.md"
    assert document.record_index == 1
    assert document.body == ""
    assert document.updated is None
    assert document.source_id == "sample"


def test_parse_document_when_value_null() -> None:
    """値を求めなかった（正常系）。"""
    # 準備
    value = list_entry(doc_json("a", "docs/a.yaml"), values=False)
    # 実行
    document = parse_document("sample", value)
    # 検証
    assert document.data == {}


def test_parse_document_when_key_missing() -> None:
    """必須のキーが無い（異常系）。"""
    # 準備
    value = list_entry(doc_json("a", "docs/a.yaml"), values=True)
    del value["version"]
    # 実行・検証
    with pytest.raises(ProjectIndexResponseError, match="version"):
        parse_document("sample", value)
