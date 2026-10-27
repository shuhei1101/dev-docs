"""新しい文書の置き場所。"""

from __future__ import annotations

from dev_docs.features.sources.types import DocumentTable


def new_document_path(table: DocumentTable, doc_id: str) -> tuple[str, bool]:
    """`create` の文書を書くファイルを、文書の行の `paths` の先頭から決める。"""
    raise NotImplementedError
