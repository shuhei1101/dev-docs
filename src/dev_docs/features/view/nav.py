"""タブとサイドバーの組み立て。"""

from __future__ import annotations

from collections.abc import Sequence

from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import ServedSource
from dev_docs.features.view.types import NavTab


def build_nav(source: ServedSource, documents: Sequence[Document]) -> list[NavTab]:
    """配信元の `nav` と文書から、上のタブとサイドバーを作る。"""
    raise NotImplementedError


def first_page(tab: NavTab) -> str | None:
    """タブのサイドバーの一番上の文書のページのパスを返す。"""
    raise NotImplementedError
