"""変換の選択と `converters[]` の実行。"""

from __future__ import annotations

from pathlib import Path

from dev_docs.features.access.types import Target
from dev_docs.features.convert.types import Converted
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.integrations.scripts import run_script

TABLE_KEY_PATTERN = r"^<!-- dev-docs-table: (?P<key>.+) -->$"
CONVERT_CACHE_KEEP = 2000

__all__ = ["CONVERT_CACHE_KEEP", "TABLE_KEY_PATTERN", "ConvertService", "run_script"]


class ConvertService:
    """文書の行の設定で変換を選び、埋め込みを展開した Markdown を返す。"""

    def __init__(self, cache_dir: Path, store: DocumentStore, timeout_sec: float) -> None:
        self.cache_dir = cache_dir
        self.store = store
        self.timeout_sec = timeout_sec

    def convert(self, target: Target, document: Document) -> Converted:
        """1 件の文書を Markdown にする。"""
        raise NotImplementedError

    def clear(self) -> None:
        """`cache_dir` の控えを全て消す。"""
        raise NotImplementedError
