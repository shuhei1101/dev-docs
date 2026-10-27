from __future__ import annotations

from dev_docs.features.sources.types import DocumentTable
from dev_docs.features.write.placement import new_document_path


def test_new_document_path() -> None:
    """glob から決める（正常系）。"""
    # 準備
    by_glob = DocumentTable(id="sample", type="yaml", paths=["docs/**/*.yaml"])
    by_records = DocumentTable(id="items", type="yaml", paths=["data/list.yaml"], records="items")
    # 実行
    glob_result = new_document_path(by_glob, "sample-doc")
    records_result = new_document_path(by_records, "item-1")
    # 検証
    assert glob_result == ("docs/sample-doc.yaml", False)
    assert records_result == ("data/list.yaml", True)
