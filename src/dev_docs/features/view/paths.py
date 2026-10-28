"""画面のパスの分解と読む場所。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from dev_docs.features.access.types import Target
from dev_docs.features.documents.types import Document
from dev_docs.features.history.query import resolve_ref
from dev_docs.features.history.types import ResolvedRef
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.view.types import ScreenPath


def parse_screen_path(source_part: str, page: str) -> ScreenPath:
    """ルートの `{source_part}` と `{page}` を画面のパスにする。"""
    source_id, _, ref = source_part.partition("@")
    return ScreenPath(source_id=source_id, ref=ref or None, page=page.strip("/"))


def page_path(document: Document) -> str:
    """文書を URL のパスにする。"""
    path = PurePosixPath(document.path).with_suffix("").as_posix()
    if document.record_index is not None:
        return f"{path}/{document.id}"
    return path


def find_page(documents: Sequence[Document], page: str) -> Document | None:
    """文書のページのパスに当たる文書を探す。"""
    return next((document for document in documents if page_path(document) == page), None)


def screen_target(
    source_id: str, ref: str | None, *, registry: SourceRegistry
) -> tuple[Target, ResolvedRef | None]:
    """画面のパスの配信元とリビジョンから読む場所を作る。"""
    source = registry.get(source_id)
    # 画面は 127.0.0.1 だけで待ち受けるので、作業場所の権限は見ない
    if not source.is_git or source.repo_root is None:
        return Target(source, source.root, None, None, "read"), None
    default_ref = source.config.default_ref
    resolved = resolve_ref(source.repo_root, ref or default_ref, date_base=default_ref)
    return Target(source, source.root, resolved.commit, None, "read"), resolved


def breadcrumbs(page: str, pages: Sequence[str]) -> list[tuple[str, str | None]]:
    """文書のページのパスを階層ごとの名前とリンク先にする。"""
    segments = page.split("/") if page else []
    crumbs: list[tuple[str, str | None]] = []
    for depth, name in enumerate(segments, start=1):
        if depth == len(segments):
            crumbs.append((name, None))
            continue
        prefix = "/".join(segments[:depth])
        link = next((candidate for candidate in pages if candidate.startswith(f"{prefix}/")), None)
        crumbs.append((name, link))
    return crumbs
