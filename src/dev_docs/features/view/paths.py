"""画面のパスの分解と読む場所。"""

from __future__ import annotations

from collections.abc import Sequence

from dev_docs.features.access.types import Target
from dev_docs.features.documents.types import Document
from dev_docs.features.history.types import ResolvedRef
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.view.types import ScreenPath


def parse_screen_path(source_part: str, page: str) -> ScreenPath:
    """ルートの `{source_part}` と `{page}` を画面のパスにする。"""
    raise NotImplementedError


def page_path(document: Document) -> str:
    """文書を URL のパスにする。"""
    raise NotImplementedError


def find_page(documents: Sequence[Document], page: str) -> Document | None:
    """文書のページのパスに当たる文書を探す。"""
    raise NotImplementedError


def screen_target(
    source_id: str, ref: str | None, *, registry: SourceRegistry
) -> tuple[Target, ResolvedRef | None]:
    """画面のパスの配信元とリビジョンから読む場所を作る。"""
    raise NotImplementedError


def breadcrumbs(page: str, pages: Sequence[str]) -> list[tuple[str, str | None]]:
    """文書のページのパスを階層ごとの名前とリンク先にする。"""
    raise NotImplementedError
