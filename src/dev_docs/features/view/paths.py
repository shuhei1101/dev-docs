"""文書のページのパスと、文書のページの特定。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from dev_docs.integrations.project_index.types import IndexedDocument, SearchHit


def page_path(document: IndexedDocument | SearchHit) -> str:
    """文書を URL のパスにする。"""
    path = PurePosixPath(document.path).with_suffix("").as_posix()
    if document.record_index is not None:
        return f"{path}/{document.id}"
    return path


def find_page(documents: Sequence[IndexedDocument], page: str) -> IndexedDocument | None:
    """文書のページのパスに該当する文書を探す。

    無ければ、文書のファイルか本文のファイルのパスが `page` と同じ最初の文書を返却する
    （画面が本文の相対リンクを本文のファイルのパスで解決して指定するため）。
    """
    found = next((document for document in documents if page_path(document) == page), None)
    if found is not None:
        return found
    return next(
        (document for document in documents if page in (document.path, document.body_path)),
        None,
    )
