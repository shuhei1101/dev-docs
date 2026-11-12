from __future__ import annotations

from datetime import datetime

import pytest

from dev_docs.integrations.project_index.types import parse_document
from dev_docs.shared.errors import ProjectIndexResponseError

from ...conftest import doc_json


def test_parse_document() -> None:
    """全てのキーを読み取る（正常系）。"""
    # 準備
    value = doc_json(
        "n-1",
        "notes/files.yaml",
        record_index=1,
        body_path="notes/a.md",
        updated="2026-11-12T10:00:00+09:00",
    )
    # 実行
    document = parse_document("sample", value)
    # 検証
    assert document.record_index == 1
    assert document.body_path == "notes/a.md"
    assert document.updated == datetime.fromisoformat("2026-11-12T10:00:00+09:00")
    assert document.updated.tzinfo is not None
    assert document.body == ""
    assert document.source_id == "sample"


def test_parse_document_when_key_missing() -> None:
    """必須のキーが無い（異常系）。"""
    # 準備
    value = doc_json("a", "docs/a.yaml")
    del value["version"]
    # 実行・検証
    with pytest.raises(ProjectIndexResponseError, match="version"):
        parse_document("sample", value)
