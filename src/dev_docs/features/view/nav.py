"""タブとサイドバーの組み立て。"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.features.documents.fields import get_field
from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable, ServedSource
from dev_docs.features.view.paths import page_path
from dev_docs.features.view.types import NavGroup, NavLink, NavTab

logger = logging.getLogger(__name__)

OTHER_GROUP = "その他"


def _link(document: Document, title: str | None = None) -> NavLink:
    """文書をサイドバーの 1 行にする。"""
    return NavLink(
        title=title or str(document.metadata.get("name") or document.id),
        page=page_path(document),
    )


def _documents_of(documents: Sequence[Document], kind: str) -> list[Document]:
    """文書の行の文書を、文書のページのパスの昇順で返す。"""
    return sorted((d for d in documents if d.kind == kind), key=page_path)


def _auto(documents: Sequence[Document], spec: Mapping[str, Any]) -> NavGroup:
    """`auto` の文書を並べる（`group_by` があれば値ごとの見出しにする）。"""
    found = _documents_of(documents, str(spec.get("document", "")))
    group_by = spec.get("group_by")
    if not group_by:
        return NavGroup(title=None, links=[_link(document) for document in found])
    buckets: dict[str, list[NavLink]] = {}
    for document in found:
        value = get_field(document.data, str(group_by))
        names = (
            [str(item) for item in value]
            if isinstance(value, list)
            else [str(value)]
            if value
            else [OTHER_GROUP]
        )
        for name in dict.fromkeys(names or [OTHER_GROUP]):
            buckets.setdefault(name, []).append(_link(document))
    return NavGroup(
        title=None,
        groups=[NavGroup(title=name, links=links) for name, links in buckets.items()],
    )


def _page(source: ServedSource, documents: Sequence[Document], value: str) -> Document | None:
    """`page` の値（行の id か `{行の id}/{文書の ID}`）が指す文書を探す。"""
    kind, _, doc_id = value.partition("/")
    rows = {row.id: row for row in source.config.documents}
    if kind not in rows:
        return None
    found = _documents_of(documents, kind)
    if not doc_id:
        return found[0] if len(found) == 1 else None
    return next((d for d in found if d.id == doc_id), None)


def _items(
    source: ServedSource, documents: Sequence[Document], items: Sequence[Mapping[str, Any]]
) -> NavGroup:
    """`items[]` を上から読み、見出しのない根の見出しを作る。"""
    root = NavGroup(title=None)
    for item in items:
        if "group" in item:
            child = _items(source, documents, item.get("items") or [])
            root.groups.append(
                NavGroup(title=str(item["group"]), links=child.links, groups=child.groups)
            )
        elif "page" in item:
            document = _page(source, documents, str(item["page"]))
            if document is None:
                logger.warning("nav の文書が無い（%s・%s）", source.id, item["page"])
                continue
            root.links.append(_link(document, item.get("title")))
        elif "auto" in item:
            auto = _auto(documents, item["auto"])
            title = item.get("title")
            if title and not auto.groups:
                auto = NavGroup(
                    title=None, links=[NavLink(title=title, page=link.page) for link in auto.links]
                )
            root.links.extend(auto.links)
            root.groups.extend(auto.groups)
    return root


def _tab_title(row: DocumentTable) -> str:
    """nav が無いときのタブの名前（行の `title`、無ければ `id`）。"""
    return row.title or row.id


def build_nav(source: ServedSource, documents: Sequence[Document]) -> list[NavTab]:
    """配信元の `nav` と文書から、上のタブとサイドバーを作る。"""
    nav = source.config.nav
    if not nav:
        return [
            NavTab(title=_tab_title(row), sidebar=_auto(documents, {"document": row.id}))
            for row in source.config.documents
            if row.enabled
        ]
    return [
        NavTab(title=str(tab["title"]), sidebar=_items(source, documents, tab.get("items") or []))
        for tab in nav.get("tabs", [])
    ]


def first_page(tab: NavTab) -> str | None:
    """タブのサイドバーの一番上の文書のページのパスを返す。"""

    def walk(group: NavGroup) -> str | None:
        if group.links:
            return group.links[0].page
        for child in group.groups:
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(tab.sidebar)
